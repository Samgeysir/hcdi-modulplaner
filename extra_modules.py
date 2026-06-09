"""
extra_modules.py — Lädt zusätzliche Module, die NICHT über die FHNW-API verfügbar sind.

Manche Studiengänge pflegen ihre Module nicht in der FHNW-Modul-API. Solche Module
werden hier aus einer JSON-Datei geladen und in app.py an die gescrapte Modul-Liste
angehängt — gleiches flaches Dashboard-Schema, sodass sie im Frontend automatisch
überall auftauchen (Filter, Vergleich, Stundenplan).

Quelle (in dieser Reihenfolge):
  1. Online: GitHub-Raw-URL `<EXTRA_MODULES_URL_BASE>/extra_modules_<sem>.json`
     -> einmal auf GitHub ändern, alle Nutzer:innen haben sofort neue Daten.
  2. Fallback lokal: `data/extra_modules_<sem>.json` neben app.py (auch offline /
     wenn GitHub nicht erreichbar). Im PyInstaller-Bundle via sys._MEIPASS.
Fehlt beides -> [] (App verhält sich unverändert, nur ohne Zusatzmodule).

Öffentlich:
  - load_extra_modules(semester_value) -> list[dict]   (normalisierte Datensätze)
"""

import os
import sys
import json
import time

import requests

import scraper_core

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# GitHub-Raw als kostenlose, statische "API". Überschreibbar per Umgebungsvariable,
# z.B. um auf einen Feature-Branch zu zeigen: .../hcdi-modulplaner/<branch>/data/
EXTRA_MODULES_URL_BASE = os.environ.get(
    "EXTRA_MODULES_URL_BASE",
    "https://raw.githubusercontent.com/Samgeysir/hcdi-modulplaner/main/data/",
)

# Soll-Feldliste: alle Schlüssel, die das Dashboard-Frontend liest. Fehlende Felder
# werden auf "" gesetzt, damit kein Datensatz Lücken hat.
_REQUIRED_FIELDS = (
    ["Hochschule", "url", "detailedLecturers"]
    + scraper_core.SEARCH_FIELDS
    + scraper_core.DETAIL_FIELDS
    + scraper_core.LEKTION_FIELDS
)

# Freitext-Felder, in denen HTML aus Excel-Exporten bereinigt werden soll.
_HTML_FIELDS = set(scraper_core.DETAIL_FIELDS)

# Kurzer In-Memory-Cache pro Semester, damit nicht jeder /api/modules-Aufruf GitHub
# trifft. TTL ~ GitHub-CDN-Cachezeit.
_CACHE_TTL = 300.0
_cache = {}  # semester -> (timestamp, list[dict])


def _resource_dir():
    """Ordner mit mitgelieferten Dateien (data/). Build-tauglich via sys._MEIPASS."""
    return getattr(sys, "_MEIPASS", APP_DIR)


def _safe(semester):
    """Gleiche Bereinigung wie app._cache_path: nur alphanumerische Zeichen."""
    return "".join(c for c in semester if c.isalnum())


def _join(v):
    """Listen -> ', '-String (wie to_dashboard_record); sonst unverändert."""
    if isinstance(v, list):
        return ", ".join(str(x) for x in v if x)
    return v if v is not None else ""


def normalize_record(raw, index=0):
    """Bringt einen rohen Zusatzmodul-Datensatz ins vollständige Dashboard-Schema.

    - alle vom Frontend gelesenen Felder existieren (fehlende -> "")
    - Listenwerte werden zu ', '-Strings gejoint
    - HTML in Freitext-Feldern wird bereinigt
    - leere planSemesterModulId -> synthetische, kollisionsfreie EXTRA_-ID
    - isExtra=True als Markierung (für optionalen Badge)
    """
    rec = {}
    for field in _REQUIRED_FIELDS:
        val = _join(raw.get(field, ""))
        if field in _HTML_FIELDS and val:
            val = scraper_core.clean_html(val)
        rec[field] = val

    if not rec.get("planSemesterModulId"):
        rec["planSemesterModulId"] = f"EXTRA_{index}"

    # Strukturierte Sitzungsliste optional durchreichen (Liste, nicht joinen).
    # Fehlt sie, leitet das Frontend Tag/Zeit aus den Flachfeldern ab.
    sessions = raw.get("lektionSessions", [])
    rec["lektionSessions"] = sessions if isinstance(sessions, list) else []

    rec["isExtra"] = True
    return rec


def _load_raw(semester_value):
    """Rohe Datensatzliste laden: erst GitHub-Raw, dann lokale Datei. [] wenn nichts."""
    fname = f"extra_modules_{_safe(semester_value)}.json"

    # 1. Online (GitHub-Raw)
    try:
        url = EXTRA_MODULES_URL_BASE.rstrip("/") + "/" + fname
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                return data
    except Exception:
        pass

    # 2. Fallback lokal
    try:
        path = os.path.join(_resource_dir(), "data", fname)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass

    return []


def load_extra_modules(semester_value):
    """Normalisierte Zusatzmodule für ein Semester. Robust: [] bei Fehlern."""
    if not semester_value:
        return []

    now = time.time()
    cached = _cache.get(semester_value)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    raw = _load_raw(semester_value)
    records = []
    for i, item in enumerate(raw):
        if isinstance(item, dict):
            records.append(normalize_record(item, index=i))

    _cache[semester_value] = (now, records)
    return records
