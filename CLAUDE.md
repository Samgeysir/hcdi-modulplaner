# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Was diese App macht

Eine eigenständige Web-App, die alle FHNW-Module live von der FHNW-API lädt und in einem
interaktiven Dashboard zur Modulplanung darstellt. Sie führt zwei früher getrennte Projekte zusammen:

- **Scraper** (vormals Streamlit-App `module_scraper_10`) → liefert die Modul-Daten von der FHNW-API
- **Dashboard** (vormals statisches HTML aus `HS 26 Module`) → Filter, Stundenplan, Vergleich, Auswahl

Der alte Workflow (Excel-Export → Online-JSON-Konverter → JSON ablegen → Build-Script) entfällt
komplett. Die Daten gehen direkt vom Backend ins Dashboard.

## App starten

```bash
# Variante A: macOS Doppelklick
run.command            # richtet beim ersten Start .venv ein, installiert Deps, öffnet Browser

# Variante B: Terminal
source .venv/bin/activate
python app.py
```

Läuft auf **http://localhost:8000** (Port hartcodiert in `app.py`). `run.command` öffnet den
Browser automatisch nach ~1,2 s.

## Abhängigkeiten installieren

```bash
pip install -r requirements.txt    # flask>=3.0.0, requests>=2.31.0
```

Kein pandas/openpyxl/streamlit mehr — die App braucht nur Flask + requests.

## Repository-Aufbau

```
app.py                   — Flask-Server: Dashboard ausliefern + JSON-API + Hintergrund-Scrape + Cache
scraper_core.py          — Reine FHNW-Scraping-Logik (ohne UI), liefert Dashboard-Schema
templates/dashboard.html — Dashboard-Frontend (HTML/CSS/JS), holt Daten per fetch vom Backend
cache/                   — Pro-Semester JSON-Cache: modules_<Semester>.json (in .gitignore)
requirements.txt         — Abhängigkeiten
run.command              — macOS-Doppelklick-Starter (auto-venv)
README.md                — Endnutzer-Anleitung (Deutsch)
```

## Architektur

### Backend (`app.py`)
Flask-App, ein Prozess. Zustand in modulglobalem `STATUS`-Dict (pro Semester), kein DB.
Hintergrund-Scrapes laufen in `threading.Thread` (daemon). Ergebnis wird nach
`cache/modules_<Semester>.json` persistiert → Neustart lädt sofort aus Cache.

| Methode | Endpunkt | Zweck |
|---|---|---|
| GET | `/` | Liefert `templates/dashboard.html` |
| GET | `/api/semesters` | `[{value, label}]` — verfügbare Semester (aus Facetten) |
| GET | `/api/modules?semester=<v>` | Dashboard-JSON aus Cache (**200**) oder startet Scrape (**202** `{state:loading}`) |
| GET | `/api/status?semester=<v>` | `{state, phase, done, total, message, count}` |
| POST | `/api/refresh?semester=<v>` | Löscht Cache, startet Neu-Scrape (**202**) |

`state`: `idle` | `loading` | `ready` | `error`. `phase`: `search` | `details` | `done`.
Cache-Dateiname: nicht-alphanumerische Zeichen aus dem Semester-Value werden entfernt
(`_cache_path`), z.B. `26HS` → `cache/modules_26HS.json`.

### Scraper (`scraper_core.py`)
Portiert aus `module_scraper_10/fhnw_module_exporter.py`, von Streamlit entkoppelt. Öffentlich:

- `load_available_facets()` → `(universities, semesters, study_programs)`. Fällt auf hardcodierte
  Werte zurück, wenn die API nicht erreichbar ist.
- `fetch_modules(semester_data, university, uni_data)` → rohe Modul-Dicts einer Hochschule
  (paginiert, `skip/take=100`, `time.sleep(0.1)` zwischen Seiten).
- `enrich_with_details(modules, progress_cb)` → reichert in-place an,
  `ThreadPoolExecutor(max_workers=5)`; Detail- + Lektionsfelder, HTML bereinigt via `clean_html`.
- `to_dashboard_record(module, university)` → mappt ins **Dashboard-Schema**.
- `fetch_all_universities(semester_value, progress_cb)` → orchestriert alle Hochschulen +
  Details, dedupliziert auf `planSemesterModulId`, gibt Liste von Dashboard-Datensätzen zurück.
  `progress_cb(phase, done, total, message)`.

### Frontend (`templates/dashboard.html`)
Identisches Design/CSS wie das alte Dashboard. Nur die Datenanbindung wurde getauscht:

- `let MODULES_DATA = []` statt eingebackenem JSON (kein `MODULES_JSON_PLACEHOLDER` mehr).
- `DOMContentLoaded` → `initSemesterSelector()` (async): füllt das Semester-Dropdown aus
  `/api/semesters`, lädt das erste/URL-Semester via `loadSemester()`.
- `loadSemester(sem)`: `fetch /api/modules`; bei **202** `pollStatusUntilReady()` (Overlay mit
  Fortschritt), dann erneut fetchen → `MODULES_DATA` setzen → `buildDashboard()` → Overlay aus.
- `buildDashboard()` = die ursprüngliche Init-Kette. **Reihenfolge wichtig:** `renderTimetable()`
  erzeugt `#calendar-time-axis` / `#calendar-row-lines`, die `initTimetableGridLines()` danach
  füllt → render MUSS vor init laufen (siehe „Bekannte Fallstricke").
- Neue UI-Elemente im Header: `#semester-select` (Dropdown) und `#btn-refresh` (`refreshData()`).
  `#header-subtitle` zeigt das gewählte Semester. Lade-Overlay: `#load-overlay`, gesteuert über
  `showOverlay(show, message, pct)`.

## FHNW-API

Basis-URL: `https://bariapi.fhnw.ch/cit_modulbeschreibungen/prod`. Keine Auth, `timeout=10`.

| Methode | Endpunkt | Zweck |
|---|---|---|
| POST | `/api/search/facets` | Hochschulen, Semester, Studiengänge |
| POST | `/api/search` | Modul-Liste, paginiert `skip/take=100` |
| GET | `/api/PlanSemesterModul/{id}` | Modul-Details (Inhalt, Kompetenzen, Literatur …) |
| GET | `/api/Lektion/modulanlassId/{id}` | Lektionstermine/-zeiten/-räume |

## Datenmodell (Dashboard-Schema)

`to_dashboard_record()` erzeugt pro Modul ein flaches Dict. Schlüssel u.a.:
`Hochschule` (gross!), `title`/`titleEN`, `planSemesterModulId`, `ects`, `teachers`, `language`,
`studyPrograms`, `courseContent`/`...EN`, `keyIdea`, `competences`, `literature`, `requirements`,
`assessment`, `detailedLecturers`, Lektionsfelder (`lektionDates`, `lektionFirstDate`,
`lektionLastDate`, `lektionRooms`, `lektionTimeFrom`, `lektionTimeTo`, `lektionDayOfWeek`), `url`.
Listenwerte werden mit `", "` zu Strings gejoint.

**Wichtig:** Das Dashboard-JS liest `m.Hochschule` (gross). Der Scraper liefert genau das. Die
alten Roh-Exporte nutzten `hochschule` (klein) — das JS hat einen Fallback `m.Hochschule || m.hochschule`.

## Bekannte Fallstricke

- **Timetable-Init-Reihenfolge:** `renderTimetable()` baut die Kalender-Elemente per `innerHTML`;
  `initTimetableGridLines()` setzt `#calendar-time-axis.innerHTML`. Läuft init vor render, ist das
  Element `null` → `TypeError`. In `buildDashboard()` daher: erst `renderTimetable()`, dann
  `initTimetableGridLines()`. (Im alten statischen Dashboard war dieser Fehler latent vorhanden,
  blieb aber unsichtbar.)
- **Erstes Laden dauert:** „alle Hochschulen + Details" für ein Semester sind mehrere Minuten
  (~3 Module/s pro Hochschule, 6 Hochschulen). Danach Cache → sofort. `refresh` erzwingt neu.
- **Offline:** ohne Internet liefert `load_available_facets()` hardcodierte Fallback-Semester;
  `/api/modules` für ein ungecachtes Semester endet dann im `error`-Status.

## GitHub & Arbeitsweise

### Commits
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, etc.
- Keep subject line under 72 characters
- Write in imperative mood ("Add feature" not "Added feature")
- Reference issues: `fixes #123`

### Branches
- Feature branches: `feat/<short-description>`
- Bug fixes: `fix/<short-description>`
- Never commit directly to `main` or `develop`

### Pull Requests
- Keep PRs small and focused (one concern per PR)
- Write a clear description explaining *why*, not just *what*
- Link related issues
- Ensure CI passes before requesting review

### Code Review
- Respond to all review comments before merging
- Squash fixup commits before merge

### Was ins Repo gehört (und was nicht)
Getrackt: Quellcode (`app.py`, `scraper_core.py`, `templates/dashboard.html`), `requirements.txt`,
`run.command`, `README.md`, `CLAUDE.md`, `cache/.gitkeep`.
Per `.gitignore` ausgeschlossen: `.venv/`, `__pycache__/`, `cache/*.json` (gescrapte Daten),
`.DS_Store`. → Das Repo enthält **keine** Modul-Daten und keine virtuelle Umgebung; beides entsteht
zur Laufzeit. `cache/.gitkeep` hält nur den leeren `cache/`-Ordner im Repo.

### Standard-Workflow für Änderungen
```bash
# Änderungen lokal testen (python app.py), dann:
git add <geänderte Dateien>
git commit -m "Kurze Beschreibung was und warum"
git push                        # in den eigenen Remote (origin)
```
Commit-Messages auf Deutsch, präsens/imperativ („füge Windows-Starter hinzu", „behebe …").
Vor dem Push lokal testen (App starten, Dashboard im Browser prüfen).

### Wichtige Konventionen
- **Nicht pushen ohne ausdrückliches OK der jeweiligen Person.** Lokal committen ist ok;
  `git push` nur auf Aufforderung.
- **Keine Cache-JSON oder `.venv` committen** (sind absichtlich ignoriert). Falls bewusst eine
  Demo-Cache-Datei mitgeliefert werden soll, mit `git add -f cache/modules_<sem>.json` erzwingen —
  vorher abklären (Datei ~8 MB, Daten veralten).
- Größere Änderungen idealerweise als eigener Branch + PR (`gh pr create`), kleine Fixes direkt auf
  `main`.

## Verteilung an Mitstudent:innen

Den Repo-Link (aus `git remote -v` oder GitHub-Weboberfläche) teilen:
```bash
git clone <repo-url>
cd <repo-ordner>
# macOS: Doppelklick run.command  |  sonst: pip install -r requirements.txt && python app.py
```
Beim ersten Start scrapt die App das gewählte Semester selbst (einige Minuten), danach Cache.
Alternativ Ordner als ZIP weitergeben; eine gefüllte `cache/modules_*.json` kann separat
mitgegeben werden, damit das Dashboard sofort Daten zeigt.

Offen (siehe Backlog-Ideen): `run.bat` für Windows-Nutzer:innen ergänzen.

## Entwickelt für

FHNW MSc Human-Centered Digital Innovation.
