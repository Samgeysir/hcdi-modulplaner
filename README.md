# FHNW Modulplaner

Eine App, die alle FHNW-Module live von der FHNW-API lädt und in einem interaktiven
Dashboard zur Modulplanung darstellt — **ohne** Excel-Export, JSON-Konvertierung oder
manuelle Build-Schritte. Semester sind frei wählbar; die Daten werden im Hintergrund
geladen und pro Semester zwischengespeichert.

## Schnellstart (macOS)

1. **Python 3** installieren (falls noch nicht vorhanden): <https://www.python.org/downloads/>
2. Doppelklick auf **`run.command`**.
   - Beim ersten Start wird automatisch eine virtuelle Umgebung erstellt und die
     Abhängigkeiten (`flask`, `requests`) installiert.
   - Danach öffnet sich das Dashboard automatisch unter <http://localhost:8000>.
3. Fenster offen lassen, solange du die App nutzt. Zum Beenden: **Strg+C** oder Fenster schliessen.

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

Dann <http://localhost:8000> im Browser öffnen.

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
├── requirements.txt        # Abhängigkeiten
├── run.command             # macOS-Doppelklick-Starter
└── README.md
```

## Datenquelle

Öffentliche FHNW-API: `https://bariapi.fhnw.ch/cit_modulbeschreibungen/prod`
(keine Authentifizierung nötig). Es wird nur lesend zugegriffen.
