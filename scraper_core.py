"""
scraper_core.py — Reine FHNW-Modul-Scraping-Logik (ohne Streamlit / UI).

Portiert aus module_scraper_10/fhnw_module_exporter.py. Liefert Module direkt im
Dashboard-Schema (Schlüssel "Hochschule" gross, plus "url"), sodass das Frontend die
Daten ohne Zwischenschritt verwenden kann.

Öffentliche Funktionen:
  - load_available_facets()            -> (universities, semesters, study_programs)
  - fetch_all_universities(sem, cb)    -> list[dict]  (alle Hochschulen + Details, dedupliziert)
  - fetch_modules(sem_data, uni, ...)  -> list[dict]  (rohe Modul-Dicts einer Hochschule)
"""

import re
import json
import time
from html import unescape
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

BASE = "https://bariapi.fhnw.ch/cit_modulbeschreibungen/prod"
# Parallele Detail-Requests. Live-Messung gegen die FHNW-API: Durchsatz plateauiert
# bei ~10-12 req/s, getestet bis 40 Worker ohne Fehler/429. 10 = Sweet Spot (nutzt
# das Limit aus, moderate Last). Die Hochschulen-Schleife bleibt bewusst sequenziell,
# damit die Gesamt-Parallelität nicht auf 6×10 hochmultipliziert.
DETAIL_WORKERS = 10
MODULE_URL_BASE = "https://modulbeschreibungen.webapps.fhnw.ch/detail/"

# Felder, die im Dashboard-Datensatz landen (Reihenfolge egal, JS liest per Name).
DETAIL_FIELDS = [
    "courseContent", "courseContentEN", "keyIdea", "keyIdeaEN",
    "competences", "competencesEN", "learningStudyMethod", "learningStudyMethodEN",
    "literature", "literatureEN", "requirements", "requirementsEN",
    "remarks", "remarksEN", "assessment", "assessmentEN",
    "compulsoryAttendance", "compulsoryAttendanceEN",
]
LEKTION_FIELDS = [
    "lektionDates", "lektionFirstDate", "lektionLastDate",
    "lektionRooms", "lektionTimeFrom", "lektionTimeTo", "lektionDayOfWeek",
]
# Felder aus der Suchantwort, die direkt ins Dashboard übernommen werden.
SEARCH_FIELDS = [
    "title", "titleEN", "planSemesterModulId", "ects", "language",
    "teachers", "studyPrograms", "studyProgramsEN", "locations",
    "moduleTypes", "moduleTypesEN", "studyLevel", "organizer",
    "moduleResponsibles", "performanceRecords",
]


# ---------------------------------------------------------------------------
# Hilfsfunktionen (1:1 aus dem Original)
# ---------------------------------------------------------------------------
def clean_html(html_text):
    """Entfernt HTML-Tags und bereinigt Text."""
    if not html_text or html_text == "None":
        return ""
    text = re.sub(r"<[^>]+>", "", str(html_text))
    text = unescape(text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def format_performance_records(raw):
    """Parst den JSON-kodierten performanceRecords-String in lesbaren Text."""
    if not raw:
        return ""
    try:
        records = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(records, list):
            return str(raw)
        parts = []
        for r in records:
            art = r.get("AssessmentType") or r.get("LeistungsnachweisArt") or ""
            pruef = r.get("ExamType") or r.get("Pruefungsart") or ""
            dauer = r.get("Duration") or r.get("Dauer") or ""
            zeitpunkt = r.get("ExaminationPeriod") or r.get("Zeitpunkt") or ""
            gewichtung = r.get("Weighting") or r.get("Gewichtung") or ""
            details = [x for x in [pruef, (f"{dauer} Min." if dauer else ""), gewichtung, zeitpunkt] if x]
            parts.append(f"{art} ({', '.join(details)})" if details else art)
        return " | ".join(p for p in parts if p)
    except (json.JSONDecodeError, TypeError):
        return str(raw)


def load_module_details(plan_semester_modul_id):
    url = f"{BASE}/api/PlanSemesterModul/{plan_semester_modul_id}"
    try:
        r = requests.get(url, timeout=10)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def load_lektion_details(modulanlass_id):
    url = f"{BASE}/api/Lektion/modulanlassId/{modulanlass_id}"
    try:
        r = requests.get(url, timeout=10)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Facetten: Hochschulen, Semester, Studiengänge
# ---------------------------------------------------------------------------
def load_available_facets():
    """Lädt verfügbare Hochschulen, Semester und Studiengänge von der API.
    Gibt (universities, semesters, study_programs) zurück. Fällt auf hardcodierte
    Werte zurück, wenn die API nicht erreichbar ist."""
    universities, semesters, study_programs = {}, {}, {}
    try:
        r = requests.post(f"{BASE}/api/search/facets", json={}, timeout=10)
        if r.status_code == 200:
            for facet in r.json().get("facetResults", []):
                name = facet.get("name")
                if name == "translated_University":
                    for v in facet.get("values", []):
                        de, en, val = v.get("displayValueGerman", ""), v.get("displayValueEnglish", ""), v.get("value", "")
                        if de and val:
                            universities[de] = {"en": en or de, "value": val}
                elif name == "translated_SemesterId":
                    for v in facet.get("values", []):
                        de, en, val = v.get("displayValueGerman", ""), v.get("displayValueEnglish", ""), v.get("value", "")
                        if de and val:
                            semesters[f"{de} ({val})"] = {"value": val, "en": en or de, "de": de}
                elif name == "translated_StudyPrograms":
                    for v in facet.get("values", []):
                        de, en, val = v.get("displayValueGerman", ""), v.get("displayValueEnglish", ""), v.get("value", "")
                        if de and val:
                            study_programs[de] = {"en": en or de, "value": val}
            if universities and semesters:
                return universities, semesters, study_programs
    except Exception:
        pass

    # Fallback
    universities = {
        "Hochschule für Gestaltung und Kunst Basel FHNW": {"en": "Basel Academy of Art and Design FHNW", "value": "Hochschule für Gestaltung und Kunst Basel FHNW"},
        "Hochschule für Wirtschaft FHNW": {"en": "School of Business FHNW", "value": "Hochschule für Wirtschaft FHNW"},
        "Hochschule für Technik FHNW": {"en": "School of Engineering FHNW", "value": "Hochschule für Technik FHNW"},
    }
    semesters = {
        "Herbstsemester 2026 (26HS)": {"value": "26HS", "en": "Autumn Semester 2026", "de": "Herbstsemester 2026"},
        "Frühlingssemester 2026 (26FS)": {"value": "26FS", "en": "Spring Semester 2026", "de": "Frühlingssemester 2026"},
        "Herbstsemester 2025 (25HS)": {"value": "25HS", "en": "Autumn Semester 2025", "de": "Herbstsemester 2025"},
    }
    return universities, semesters, study_programs


# ---------------------------------------------------------------------------
# Modul-Suche (Paginierung)
# ---------------------------------------------------------------------------
def fetch_modules(semester_data, university, uni_data):
    """Lädt alle Module einer Hochschule für ein Semester (paginiert). Rohe Dicts."""
    url = f"{BASE}/api/search"
    facet_query = [
        {"name": "translated_SemesterId", "values": [{
            "displayValueEnglish": semester_data["en"],
            "displayValueGerman": semester_data["de"],
            "value": semester_data["value"]}]},
        {"name": "translated_University", "values": [{
            "displayValueEnglish": uni_data["en"],
            "displayValueGerman": university,
            "value": uni_data["value"]}]},
    ]
    payload = {"searchQuery": {"searchText": "", "facetQuery": facet_query},
               "pagingQuery": {"skip": 0, "take": 100}}

    all_modules, skip = [], 0
    first = requests.post(url, json=payload, timeout=30)
    total_count = first.json().get("resultsCount", 0)
    if total_count == 0:
        return []
    while True:
        payload["pagingQuery"]["skip"] = skip
        data = requests.post(url, json=payload, timeout=30).json()
        results = data.get("currentPageSearchResults", [])
        all_modules.extend(results)
        if len(all_modules) >= total_count or len(results) == 0:
            break
        skip += 100
        time.sleep(0.1)
    return all_modules


# ---------------------------------------------------------------------------
# Detail-Anreicherung (parallel)
# ---------------------------------------------------------------------------
def _enrich_single(module):
    """Reichert ein Modul-Dict in-place mit Detail- und Lektionsfeldern an."""
    module_id = module.get("planSemesterModulId")
    if not module_id:
        return module
    details = load_module_details(module_id)
    if not details:
        return module

    if details.get("ects") and details.get("ects") > 0:
        module["ects"] = details["ects"]
    for field in ("teachers", "studyPrograms", "language"):
        if not module.get(field) and details.get(field):
            module[field] = details[field]
    for field in DETAIL_FIELDS:
        if field in details:
            module[field] = clean_html(details.get(field))
    if "performanceRecords" in details:
        module["performanceRecords"] = format_performance_records(details.get("performanceRecords"))

    if details.get("moduleInstances"):
        lecturers, modulanlass_ids = [], []
        for inst in details["moduleInstances"]:
            for lec in inst.get("lecturers", []):
                name = f"{lec.get('firstName', '')} {lec.get('lastName', '')}".strip()
                if name and name not in lecturers:
                    lecturers.append(name)
            if inst.get("modulanlassId"):
                modulanlass_ids.append(inst["modulanlassId"])
        if lecturers:
            module["detailedLecturers"] = ", ".join(lecturers)

        if modulanlass_ids:
            all_lektionen, rooms_list = [], []
            for mid in modulanlass_ids:
                lek = load_lektion_details(mid)
                if lek and isinstance(lek, list):
                    all_lektionen.extend(lek)
            if all_lektionen:
                dates = sorted({l.get("lektionDate", "") for l in all_lektionen if l.get("lektionDate")})
                for lek in all_lektionen:
                    for room in lek.get("rooms", []):
                        rn = room.get("bezeichnung", "")
                        if rn and rn not in rooms_list:
                            rooms_list.append(rn)
                if dates:
                    module["lektionDates"] = ", ".join(dates)
                    module["lektionFirstDate"] = dates[0]
                    module["lektionLastDate"] = dates[-1]
                if rooms_list:
                    module["lektionRooms"] = ", ".join(rooms_list)
                first = all_lektionen[0]
                module["lektionTimeFrom"] = first.get("lektionVon", "")
                module["lektionTimeTo"] = first.get("lektionBis", "")
                module["lektionDayOfWeek"] = first.get("lektionDayOfWeek", "")
            else:
                for inst in details["moduleInstances"]:
                    if inst.get("day") and not module.get("lektionDayOfWeek"):
                        module["lektionDayOfWeek"] = inst["day"]
                    start = inst.get("startTime", "")
                    if start and not module.get("lektionTimeFrom"):
                        try:
                            module["lektionTimeFrom"] = start.split("T")[1][:5]
                        except (IndexError, AttributeError):
                            pass
                    end = inst.get("endTime", "")
                    if end and not module.get("lektionTimeTo"):
                        try:
                            module["lektionTimeTo"] = end.split("T")[1][:5]
                        except (IndexError, AttributeError):
                            pass
                    loc = inst.get("location", "")
                    if loc and loc not in rooms_list:
                        rooms_list.append(loc)
                if rooms_list:
                    module["lektionRooms"] = ", ".join(rooms_list)
    return module


def enrich_with_details(modules, progress_cb=None):
    """Reichert alle Module parallel mit Details an. progress_cb(done, total, title).

    Da die Anreicherung parallel läuft (mehrere Worker), ist `title` der Titel
    des zuletzt fertig geladenen Moduls, nicht „das eine" gerade aktive.
    """
    total = len(modules)
    done = 0
    with ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as ex:
        future_to_idx = {ex.submit(_enrich_single, m): i for i, m in enumerate(modules)}
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                modules[idx] = future.result()
            except Exception:
                pass
            done += 1
            if progress_cb:
                title = modules[idx].get("title") or ""
                progress_cb(done, total, title)
    return modules


# ---------------------------------------------------------------------------
# Mapping ins Dashboard-Schema
# ---------------------------------------------------------------------------
def to_dashboard_record(module, university):
    """Wandelt ein angereichertes Modul-Dict in einen Dashboard-Datensatz um.
    Schlüssel "Hochschule" (gross), Listen als ', '-String, plus url-Feld."""
    rec = {"Hochschule": university}

    def join(v):
        if isinstance(v, list):
            return ", ".join(str(x) for x in v if x)
        return v if v is not None else ""

    for field in SEARCH_FIELDS + DETAIL_FIELDS + LEKTION_FIELDS + ["detailedLecturers"]:
        rec[field] = join(module.get(field, ""))

    module_id = module.get("planSemesterModulId", "")
    if module_id:
        semester = module_id.split("_")[0]
        uni_enc = university.replace(" ", "%20")
        rec["url"] = f"{MODULE_URL_BASE}{module_id}?semester={semester}&university={uni_enc}"
    else:
        rec["url"] = ""
    return rec


# ---------------------------------------------------------------------------
# Orchestrierung: alle Hochschulen + Details für ein Semester
# ---------------------------------------------------------------------------
def fetch_all_universities(semester_value, progress_cb=None):
    """Lädt alle Hochschulen eines Semesters mit Details und gibt eine
    deduplizierte Liste von Dashboard-Datensätzen zurück.

    progress_cb(phase, done, total, message, title="") — optional, für Live-
    Fortschritt. `title` ist in der details-Phase der blanke Modul-Titel des
    zuletzt fertig geladenen Moduls (für die Live-Liste), sonst leer.
    """
    universities, semesters, _ = load_available_facets()

    # Semester-Daten anhand des value finden (z.B. "26HS")
    sem_data = None
    for s in semesters.values():
        if s["value"] == semester_value:
            sem_data = s
            break
    if sem_data is None:
        sem_data = {"value": semester_value, "en": semester_value, "de": semester_value}

    uni_names = list(universities.keys())
    records_by_id = {}
    n_unis = len(uni_names)

    for i, uni in enumerate(uni_names):
        if progress_cb:
            progress_cb("search", i, n_unis, f"Lade Module: {uni}")
        try:
            raw = fetch_modules(sem_data, uni, universities[uni])
        except Exception:
            raw = []
        if not raw:
            continue

        def _cb(done, total, title="", _uni=uni, _i=i):
            if progress_cb:
                if title:
                    msg = f"Geladen: {title} ({_uni}, {_i + 1}/{n_unis})"
                else:
                    msg = f"Details {_uni} ({_i + 1}/{n_unis})"
                # 5. Arg: blanker Titel für die Live-Liste im Ladescreen
                progress_cb("details", done, total, msg, title)

        enrich_with_details(raw, progress_cb=_cb)

        for m in raw:
            rec = to_dashboard_record(m, uni)
            mid = rec.get("planSemesterModulId") or id(rec)
            records_by_id.setdefault(mid, rec)

    if progress_cb:
        progress_cb("done", n_unis, n_unis, f"{len(records_by_id)} Module geladen")
    return list(records_by_id.values())
