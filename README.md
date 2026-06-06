# FHNW Modulplaner

Eine App, die alle FHNW-Module live von der FHNW-API lädt und in einem interaktiven
Dashboard zur Modulplanung darstellt — **ohne** Excel-Export, JSON-Konvertierung oder
manuelle Build-Schritte. Semester sind frei wählbar; die Daten werden im Hintergrund
geladen und pro Semester zwischengespeichert.

## Fertige App herunterladen (kein Python nötig)

Für die meisten Nutzer:innen der einfachste Weg — **eigenständige App, einfach doppelklicken**:

1. Auf der **[Releases-Seite](../../releases)** das passende Paket herunterladen:
   - **macOS:** `Modulplaner-macos.zip` → entpacken → `Modulplaner.app`
   - **Windows:** `Modulplaner.exe`
2. **Doppelklick.** Das Dashboard öffnet sich in einem **eigenen App-Fenster** (kein Browser nötig).
3. Beenden wie jede andere App: **Fenster schliessen** (rotes X bzw. **Cmd+Q** auf macOS,
   **Alt+F4** auf Windows). Damit wird auch der Hintergrund-Server beendet.

> **Erststart-Hinweis (unsignierte App):**
> - macOS: Rechtsklick auf `Modulplaner.app` → **Öffnen** → bestätigen (nur beim ersten Mal).
> - Windows: Bei „Der Computer wurde geschützt" → **Weitere Informationen** → **Trotzdem ausführen**.

Beim ersten Laden eines Semesters dauert das Scrapen einige Minuten, danach kommt alles aus dem
lokalen Cache.

## Schnellstart (macOS, mit Python)

1. **Python 3** installieren (falls noch nicht vorhanden): <https://www.python.org/downloads/>
2. Doppelklick auf **`run.command`**.
   - Beim ersten Start wird automatisch eine virtuelle Umgebung erstellt und die
     Abhängigkeiten installiert.
   - Danach öffnet sich das Dashboard in einem **eigenen App-Fenster**.
3. Beenden: **Fenster schliessen** (Cmd+Q) — beendet auch den Hintergrund-Server.

> Falls macOS „run.command kann nicht geöffnet werden" meldet:
> Rechtsklick → **Öffnen** → **Öffnen** bestätigen (nur beim ersten Mal nötig).

## Schnellstart (Windows / Linux / manuell)

```bash
cd modulplaner_app
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Das Dashboard öffnet sich in einem eigenen App-Fenster (via `pywebview`). Sollte auf einem
System kein Fenster-Backend verfügbar sein, fällt die App automatisch auf den Standardbrowser
unter <http://localhost:8000> zurück.

## Bedienung

- **Semester wählen:** Dropdown oben rechts. Beim ersten Aufruf eines Semesters werden
  alle Hochschulen mit Details geladen (kann einige Minuten dauern) — ein Fortschritts-
  Overlay zeigt den Stand. Danach kommen die Daten sofort aus dem Cache.
- **Aktualisieren:** Button „Aktualisieren" lädt die Daten des aktuellen Semesters neu
  von der FHNW-API (überschreibt den Cache).
- **Planen:** Module filtern, auswählen, im Stundenplan und in der Vergleichsansicht prüfen.

## Weitergabe an Mitstudent:innen

Den gesamten Ordner `modulplaner_app/` weitergeben (z.B. als ZIP). Wenn der Ordner
`cache/` bereits gefüllte `modules_<Semester>.json`-Dateien enthält, startet das
Dashboard sofort mit Daten — ohne dass die Empfänger:innen selbst scrapen müssen.
Sie können bei Bedarf jederzeit „Aktualisieren" oder ein anderes Semester wählen.

## Aufbau

```
modulplaner_app/
├── app.py                  # Flask-Server: Dashboard + JSON-API, Hintergrund-Scrape, Cache
├── scraper_core.py         # FHNW-Scraping-Logik (ohne UI), liefert Dashboard-Schema
├── templates/dashboard.html# Dashboard-Frontend (Live-Daten via fetch)
├── cache/                  # Pro-Semester JSON-Cache (modules_<Semester>.json)
├── requirements.txt        # Laufzeit-Abhängigkeiten (flask, requests)
├── requirements-dev.txt    # Build-Abhängigkeit (pyinstaller)
├── modulplaner.spec        # PyInstaller-Spec (.app/.exe)
├── build_mac.command       # macOS: baut dist/Modulplaner.app
├── run.command             # macOS-Doppelklick-Starter (Dev, mit Python)
└── README.md
```

## Eigenständige App selbst bauen

- **macOS:** Doppelklick auf **`build_mac.command`** → erzeugt `dist/Modulplaner.app`.
- **Windows + macOS via GitHub Actions:** Der Workflow `.github/workflows/build.yml` baut beide
  Pakete. Manuell starten unter **Actions → Build standalone apps → Run workflow** (Artefakte zum
  Download). Ein Git-Tag `v*` (z.B. `v0.1.0`) hängt die Pakete zusätzlich an ein Release.
  → So entsteht die Windows-`.exe` auch ohne Windows-Rechner.

## Datenquelle

Öffentliche FHNW-API: `https://bariapi.fhnw.ch/cit_modulbeschreibungen/prod`
(keine Authentifizierung nötig). Es wird nur lesend zugegriffen.
