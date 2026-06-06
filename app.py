"""
app.py — Flask-Backend für den FHNW Modulplaner.

Liefert das Dashboard (templates/dashboard.html) aus und stellt eine JSON-API bereit,
die die Modul-Daten live von der FHNW-API scrapt (alle Hochschulen + Details) und pro
Semester in cache/modules_<sem>.json zwischenspeichert.

Endpunkte:
  GET  /                       -> Dashboard-HTML
  GET  /api/semesters          -> [{value, label}]
  GET  /api/modules?semester=  -> Dashboard-JSON (200) oder {state:loading} (202)
  GET  /api/status?semester=   -> {state, phase, done, total, message, count}
  POST /api/refresh?semester=  -> erzwingt Neu-Scrape, startet Hintergrund-Job
"""

import os
import sys
import json
import threading
import webbrowser

from flask import Flask, jsonify, request, send_from_directory

import scraper_core

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _is_frozen():
    """True, wenn als PyInstaller-Bundle (.app/.exe) ausgeführt."""
    return getattr(sys, "frozen", False)


def _resource_dir():
    """Ordner mit mitgelieferten Dateien (templates/).

    Im PyInstaller-Bundle liegen Daten unter sys._MEIPASS, sonst neben app.py.
    """
    return getattr(sys, "_MEIPASS", APP_DIR)


def _cache_dir():
    """Schreibbarer, persistenter Cache-Ordner.

    Dev-Modus: cache/ neben app.py (unverändertes Verhalten). Gebündelt: ein
    benutzer-schreibbarer Ort, da das App-Bundle/Programmverzeichnis read-only sein kann.
    """
    if not _is_frozen():
        return os.path.join(APP_DIR, "cache")
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        return os.path.expanduser("~/.modulplaner")
    return os.path.join(base, "Modulplaner")


CACHE_DIR = _cache_dir()
TEMPLATES_DIR = os.path.join(_resource_dir(), "templates")
os.makedirs(CACHE_DIR, exist_ok=True)

app = Flask(__name__)

# Ladezustand pro Semester: {sem: {state, phase, done, total, message, count}}
# state: idle | loading | ready | error
STATUS = {}
_LOCK = threading.Lock()


def _cache_path(semester):
    safe = "".join(c for c in semester if c.isalnum())
    return os.path.join(CACHE_DIR, f"modules_{safe}.json")


def _set_status(semester, **kwargs):
    with _LOCK:
        st = STATUS.setdefault(semester, {})
        st.update(kwargs)


def _background_load(semester):
    """Scrapt alle Hochschulen + Details für ein Semester und schreibt den Cache."""
    _set_status(semester, state="loading", phase="search", done=0, total=0,
                message="Starte Laden …", count=0)

    def progress_cb(phase, done, total, message):
        _set_status(semester, state="loading", phase=phase, done=done,
                    total=total, message=message)

    try:
        records = scraper_core.fetch_all_universities(semester, progress_cb=progress_cb)
        with open(_cache_path(semester), "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False)
        _set_status(semester, state="ready", phase="done",
                    message=f"{len(records)} Module geladen", count=len(records))
    except Exception as exc:  # noqa: BLE001
        _set_status(semester, state="error", message=f"Fehler: {exc}")


def _start_load_if_needed(semester):
    """Startet einen Hintergrund-Scrape, falls nicht bereits einer läuft."""
    with _LOCK:
        st = STATUS.get(semester)
        if st and st.get("state") == "loading":
            return
        STATUS[semester] = {"state": "loading", "phase": "search",
                            "done": 0, "total": 0, "message": "Starte …", "count": 0}
    threading.Thread(target=_background_load, args=(semester,), daemon=True).start()


# ---------------------------------------------------------------------------
# Routen
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(TEMPLATES_DIR, "dashboard.html")


@app.route("/api/semesters")
def api_semesters():
    _, semesters, _ = scraper_core.load_available_facets()
    out = [{"value": data["value"], "label": label} for label, data in semesters.items()]
    return jsonify(out)


@app.route("/api/modules")
def api_modules():
    semester = request.args.get("semester", "").strip()
    if not semester:
        return jsonify({"error": "semester fehlt"}), 400

    path = _cache_path(semester)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return app.response_class(f.read(), mimetype="application/json")

    # Noch kein Cache -> Hintergrund-Scrape anstossen, 202 zurück
    _start_load_if_needed(semester)
    return jsonify({"state": "loading", "message": "Daten werden geladen …"}), 202


@app.route("/api/status")
def api_status():
    semester = request.args.get("semester", "").strip()
    st = STATUS.get(semester)
    if not st:
        # Kein laufender Job: ready, falls Cache existiert, sonst idle
        if os.path.exists(_cache_path(semester)):
            return jsonify({"state": "ready", "message": "Aus Cache"})
        return jsonify({"state": "idle", "message": "Noch nicht geladen"})
    return jsonify(st)


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    semester = request.args.get("semester", "").strip()
    if not semester:
        return jsonify({"error": "semester fehlt"}), 400
    # Cache löschen, damit /api/modules neu scrapt
    path = _cache_path(semester)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
    _start_load_if_needed(semester)
    return jsonify({"state": "loading", "message": "Neu-Laden gestartet"}), 202


def _open_browser():
    try:
        webbrowser.open("http://localhost:8000")
    except Exception:
        pass


if __name__ == "__main__":
    # Browser nur im Hauptprozess öffnen (nicht im Reloader-Kind)
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        threading.Timer(1.2, _open_browser).start()
    app.run(host="127.0.0.1", port=8000, debug=False)
