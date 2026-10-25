"""Tools exposed to the ADK agents.

Every tool returns a dict. Results that carry facts always include a
`citation` (document title, page, URL) so the agent can cite its source.
"""
import csv
import datetime as dt
import json
import re
from functools import lru_cache

import chromadb
import ollama

from helpdesk.config import (CHROMA_COLLECTION, CHROMA_DIR, EMAIL_DRAFT_DIR, EMBED_MODEL, EMBED_OPTIONS,
                             SOURCES_CSV, STRUCTURED_DIR, UNANSWERED_LOG)

# Course code scheme, Academic Regulations (D01) p.4-5, Tables 4.1-4.3:
# <2-letter dept><type letter><level digit><2-digit id><fractal digit>, e.g. MEL1XX0.
CODE_RULE_CITATION = "Academic Regulations - students enrolled from July 2019 onwards, p.4-5 (Tables 4.1-4.3)"
CODE_RE = re.compile(r"^([A-Z]{2})([A-Z])(\d)(\d{2})(\d)$")
DEPT_CODES = {  # Table 4.2
    "ME": "Mechanical Engineering", "CS": "Computer Science and Engineering",
    "EE": "Electrical Engineering", "CI": "Civil and Infrastructure Engineering",
    "CH": "Chemical Engineering", "BB": "Bioscience and Bioengineering",
    "MT": "Metallurgical & Materials Engineering", "CY": "Chemistry", "MA": "Mathematics",
    "PH": "Physics", "HS": "Humanities and Social Science", "DH": "Digital Humanities",
    "SS": "Space Science and Technology", "IO": "Internet of Things and Applications",
    "AV": "Autonomous unmanned vehicles (AUV)", "QC": "Quantum Information and Computation",
    "CG": "Cognitive Science", "SH": "Smart Healthcare", "OA": "Office of Academics",
    "OS": "Office of Students",
}


# ------------------------------------------------------------------ helpers
@lru_cache(maxsize=1)
def _sources() -> dict:
    with open(SOURCES_CSV, encoding="utf-8") as f:
        return {r["doc_id"]: r for r in csv.DictReader(f)}


def _citation(doc_id: str, page=None) -> dict:
    s = _sources().get(doc_id, {})
    return {"doc_id": doc_id, "title": s.get("title", doc_id), "page": page, "url": s.get("url", "")}


@lru_cache(maxsize=None)
def _table(name: str) -> list:
    path = STRUCTURED_DIR / name
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=1)
def _collection():
    return chromadb.PersistentClient(path=str(CHROMA_DIR)).get_collection(CHROMA_COLLECTION)


def _tokens(text: str) -> list:
    return re.findall(r"[a-z0-9]+", text.lower())


@lru_cache(maxsize=1)
def _bm25():
    """Keyword index over the same chunks stored in Chroma (for hybrid retrieval)."""
    from rank_bm25 import BM25Okapi

    data = _collection().get(include=["documents", "metadatas"])
    corpus = [_tokens(f"{m['title']} {d}") for d, m in zip(data["documents"], data["metadatas"])]
    return BM25Okapi(corpus), data["ids"], data["documents"], data["metadatas"]


def _norm_code(s: str) -> str:
    return re.sub(r"[\s\-]", "", s or "").upper()


def _semesters() -> list:
    return sorted({r["semester"] for r in _table("courses.csv")})


# Semester boundaries from the Academic Calendar AY 2026-27 (D11 p.1): "Classes Commencement"
# Semester I 30 July 2026, Semester II 4 January 2027, Summer Term 10 May 2027.
CALENDAR = [(dt.date(2026, 7, 30), "2026-27", "I"), (dt.date(2027, 1, 4), "2026-27", "II"),
            (dt.date(2027, 5, 10), "2026-27", "Summer")]


def _current_semester(today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    current = None
    for start, ay, sem in CALENDAR:
        if today >= start:
            current = (ay, sem)
    if not current:
        return {"label": "unknown (before AY 2026-27)", "academic_year": "", "semester": ""}
    ay, sem = current
    return {"label": f"AY {ay} Semester {sem}" if sem != "Summer" else f"AY {ay} Summer Term",
            "academic_year": ay, "semester": sem,
            "basis": "Academic Calendar AY 2026-27 (classes commencement dates), p.1",
            "citation": _citation("D11", 1)}


def _code_parts(code: str):
    m = CODE_RE.match(_norm_code(code))
    if not m:
        return None
    return {"dept": m.group(1), "type": m.group(2), "level": int(m.group(3)) * 100}


def _offerings(code: str) -> list:
    """Offering history of a course from faculty web pages (newest first)."""
    rows = [r for r in _table("teaching.csv") if r["course_code"] == code]
    order = {"I": 1, "II": 2, "Summer": 3}
    rows.sort(key=lambda r: (r["academic_year"], order.get(r["semester"], 0)), reverse=True)
    return [{"academic_year": r["academic_year"], "semester": r["semester"] or r["semester_label"],
             "instructor": r["instructor"], "instructor_email": r["instructor_email"],
             "text_on_page": r["context"], "citation": {"doc_id": "D30", "title": f"Web page of {r['instructor']}",
                                                        "url": r["source_url"]}} for r in rows]


# -------------------------------------------------------------------- tools
def search_documents(query: str, top_k: int = 5) -> dict:
    """Search the IIT Jodhpur document collection (academic regulations, circulars,
    academic calendars, curricula, course descriptions) for passages relevant to the query.

    Args:
        query: A focused search query, e.g. "minimum attendance requirement".
        top_k: Number of passages to return (3-5).

    Returns:
        dict with "results": a list of passages, each with doc_id, title, page, url and text.
        Cite the title and page of the passage you use.
    """
    # capped at 5: on a 4 GB GPU, generation speed drops sharply as the context grows
    top_k = max(3, min(int(top_k or 5), 5))
    pool = 30
    # dense retrieval (nomic-embed-text, query prefix as required by the model)
    emb = ollama.embed(model=EMBED_MODEL, input=[f"search_query: {query}"], options=EMBED_OPTIONS)["embeddings"][0]
    dense = _collection().query(query_embeddings=[emb], n_results=pool)
    # sparse retrieval (BM25) catches exact terms such as "Open Elective", "OE", "75%"
    bm25, ids, docs, metas = _bm25()
    scores = bm25.get_scores(_tokens(query))
    sparse_ids = [ids[i] for i in sorted(range(len(ids)), key=lambda i: -scores[i])[:pool]]
    # reciprocal rank fusion
    rrf = {}
    for rank, cid in enumerate(dense["ids"][0]):
        rrf[cid] = rrf.get(cid, 0) + 1 / (60 + rank)
    for rank, cid in enumerate(sparse_ids):
        rrf[cid] = rrf.get(cid, 0) + 1 / (60 + rank)
    by_id = {cid: (d, m) for cid, d, m in zip(ids, docs, metas)}
    out = []
    for cid in sorted(rrf, key=lambda c: -rrf[c])[:top_k]:
        text, meta = by_id[cid]
        out.append({"doc_id": meta["doc_id"], "title": meta["title"], "page": meta["page"],
                    "url": meta["url"], "text": text})
    return {"query": query, "results": out}


def lookup_course(course: str) -> dict:
    """Look up a course by code (e.g. "CSL7570") or by (part of) its name (e.g. "Autonomous Systems").

    Combines three scraped sources:
      - the official course catalogue (title, L-T-P, credits) from the Academic ERP,
      - the offering history from faculty web pages (semester, instructor),
      - the class timetable (slot, room, coordinator), published only for AY 2023-24 Semester I (1st year).

    Args:
        course: Course code or course name.

    Returns:
        dict with "found", "current_semester" and a list of "courses", each with catalogue data,
        "offerings" (newest first), "timetable" entries (with slot) and citations.
    """
    q = (course or "").strip()
    m = re.search(r"\b([A-Z]{3}\s?\d{4})\b", q.upper())
    catalogue = {r["course_code"]: r for r in _table("catalogue.csv")}
    if m:
        codes = [_norm_code(m.group(1))]
    else:
        ql = q.lower()
        codes = [c for c, r in catalogue.items() if ql and ql in r["course_title"].lower()]
        codes += [r["course_code"] for r in _table("courses.csv")
                  if ql and ql in r["course_name"].lower() and r["course_code"] not in codes]
    courses = []
    for code in codes[:6]:
        cat = catalogue.get(code)
        tt = [{**r, "citation": _citation(r["source_doc_id"])} for r in _table("courses.csv")
              if code in _norm_code(r["course_code"]).split("/")]
        offs = _offerings(code)
        if not (cat or tt or offs):
            continue
        courses.append({
            "course_code": code,
            "catalogue": ({"title": cat["course_title"], "L-T-P": f"{cat['L']}-{cat['T']}-{cat['P']}",
                           "credits": cat["credits"], "level": cat["level"], "citation": _citation("D29")}
                          if cat else None),
            "offerings": offs,
            "timetable": tt,
            "slot_available": bool(tt),
        })
    cur = _current_semester()
    if not courses:
        return {"found": False, "current_semester": cur["label"],
                "message": f"No course matching '{course}' in the course catalogue, faculty teaching pages or "
                           f"timetable. For curriculum contents use search_documents."}
    return {"found": True, "current_semester": cur["label"], "courses": courses,
            "note": "Slots are published only in the AY 2023-24 Semester I (B.Tech. 1st year) timetable; "
                    f"no slot data is public for {cur['label']}. Offerings come from faculty web pages and "
                    "may be incomplete."}


def list_courses(department_code: str = "", level: int = 0, course_type: str = "",
                 offered_in_current_semester: bool = False) -> dict:
    """List and count courses by offering department, level and type, using the official course code
    scheme (dept = first two letters, type = third letter, level = first digit x 100).

    Args:
        department_code: Two-letter department code, e.g. "HS" (Humanities and Social Science),
            "CS" (Computer Science), "MA" (Mathematics). Empty = all.
        level: Course level such as 100, 400 or 700. 0 = all levels.
        course_type: One-letter type, e.g. "L" (lecture) or "P" (practical). Empty = all.
        offered_in_current_semester: True to count only courses that faculty web pages list as
            taught in the current semester (e.g. "floated this semester"); False to count all
            courses in the official catalogue.

    Returns:
        dict with "count", "courses", the basis of the count and citations.
    """
    dept = (department_code or "").strip().upper()
    lvl = int(level or 0)
    ctype = (course_type or "").strip().upper()

    def keep(code):
        p = _code_parts(code)
        return p and (not dept or p["dept"] == dept) and (not lvl or p["level"] == lvl) \
            and (not ctype or p["type"] == ctype)

    cur = _current_semester()
    rule = {"title": CODE_RULE_CITATION, "doc_id": "D01", "page": "4-5", "url": _citation("D01")["url"]}
    filters = {"department": DEPT_CODES.get(dept, dept) or "all", "level": lvl or "all",
               "course_type": ctype or "all"}
    catalogue = {r["course_code"]: r for r in _table("catalogue.csv")}
    if offered_in_current_semester:
        rows = [r for r in _table("teaching.csv") if keep(r["course_code"])
                and r["academic_year"] == cur["academic_year"] and r["semester"] == cur["semester"]]
        found = {}
        for r in rows:
            found.setdefault(r["course_code"], {"course_code": r["course_code"],
                                                "title": catalogue.get(r["course_code"], {}).get("course_title")
                                                or r["course_title_on_page"],
                                                "instructors": set(), "sources": set()})
            found[r["course_code"]]["instructors"].add(r["instructor"])
            found[r["course_code"]]["sources"].add(r["source_url"])
        courses = [{**c, "instructors": sorted(c["instructors"]), "sources": sorted(c["sources"])}
                   for c in found.values()]
        pages = len({r["instructor"] for r in _table("teaching.csv")})
        return {"filters": filters, "semester": cur["label"], "count": len(courses), "courses": courses,
                "basis": f"Courses listed as taught in {cur['label']} on faculty web pages ({pages} faculty "
                         "publish teaching lists). The official list of floated courses is not public, so this "
                         "count is a lower bound and may be incomplete.",
                "citations": [cur["citation"], _citation("D30"), rule]}
    courses = [{"course_code": c, "title": r["course_title"], "credits": r["credits"]}
               for c, r in sorted(catalogue.items()) if keep(c)]
    return {"filters": filters, "count": len(courses), "courses": courses[:60],
            "basis": "All courses in the official course catalogue (approved courses, not the courses floated "
                     "in a particular semester).",
            "citations": [_citation("D29"), rule]}


def get_slot_timings(slot: str) -> dict:
    """Get the days and times at which a timetable slot (e.g. "G", "K", "M3") meets.

    Args:
        slot: Slot name as used in the timetable.

    Returns:
        dict with the meeting days/times, the semester of the slot grid and a citation.
    """
    s = (slot or "").strip().upper()
    rows = [r for r in _table("slots.csv") if r["slot"].upper() == s]
    if not rows:
        return {"found": False, "message": f"Slot '{slot}' not found in the slot grid ({_semesters()})."}
    return {"found": True, "slot": s,
            "meetings": [{"day": r["day"], "time": r["time"], "cell_text": r["cell_text"],
                          "semester": r["semester"]} for r in rows],
            "citation": _citation(rows[0]["source_doc_id"])}


def _faculty_by_name(name: str) -> list:
    """Faculty whose name contains all query words, or whose full name appears inside the query
    (so a whole sentence such as "email of Prof. Anand Mishra" also matches)."""
    toks = [t for t in re.split(r"\W+", name.lower()) if len(t) > 1 and t not in {"dr", "prof"}]
    qset = set(toks)
    out = []
    for f in _table("faculty.csv"):
        ftoks = [t for t in re.split(r"\W+", f["name"].lower()) if len(t) > 1]
        if toks and (all(t in f["name"].lower() for t in toks) or (len(ftoks) >= 2 and set(ftoks) <= qset)):
            out.append({"instructor": f["name"], "designation": f["designation"], "department": f["department"],
                        "email": f["email"],
                        "citation": {**_citation(f["source_doc_id"]),
                                     "url": f["profile_url"] or _citation(f["source_doc_id"])["url"]}})
    return out


def get_instructor_email(course_code: str = "", instructor_name: str = "") -> dict:
    """Find the email ID of a course's instructor (by course code) or of a faculty member (by name).

    For a course code, the instructor comes from the class timetable if the course is in it, otherwise
    from the most recent offering listed on faculty web pages (with its semester). Emails come from the
    official IIT Jodhpur People directory.

    Args:
        course_code: Course code, e.g. "CSL7570". Optional if instructor_name is given.
        instructor_name: Faculty name or part of it, e.g. "Anand Mishra". Optional if course_code is given.

    Returns:
        dict with instructor name(s), email(s), the semester the information refers to and citations,
        or found=False.
    """
    results = []
    if course_code:
        c = lookup_course(course_code)
        if c["found"]:
            course = c["courses"][0]
            for r in course["timetable"]:
                results.append({"course_code": r["course_code"], "course_name": r["course_name"],
                                "instructor": r["instructor"], "email": r["instructor_email"],
                                "semester": r["semester"], "basis": "class timetable",
                                "citation": r["citation"]})
            if not results and course["offerings"]:
                latest = course["offerings"][0]
                same = [o for o in course["offerings"] if (o["academic_year"], o["semester"])
                        == (latest["academic_year"], latest["semester"])]
                for o in same:
                    results.append({"course_code": course["course_code"],
                                    "course_name": (course["catalogue"] or {}).get("title", ""),
                                    "instructor": o["instructor"], "email": o["instructor_email"],
                                    "semester": f"AY {o['academic_year']} Semester {o['semester']}",
                                    "basis": "most recent offering listed on faculty web pages; the current "
                                             "semester's instructor is not published",
                                    "citation": o["citation"]})
    if instructor_name and not any(r.get("email") for r in results):
        results += _faculty_by_name(instructor_name)
    if not results:
        return {"found": False, "message": "No instructor found for this course/name in the timetable, faculty "
                                           "teaching pages or People directory."}
    return {"found": True, "current_semester": _current_semester()["label"], "results": results}


def draft_email(to_email: str, instructor_name: str, course_code: str, purpose: str,
                details: str, student_name: str = "", roll_number: str = "") -> dict:
    """Write an email draft for the student to review. The email is NOT sent; it is saved
    to outputs/email_drafts/. Use only facts supplied by the student or returned by tools.

    Args:
        to_email: Instructor email address (from get_instructor_email).
        instructor_name: Instructor name.
        course_code: Course code the email is about.
        purpose: Short purpose, e.g. "Sick leave for 2 days" or "Permission for makeup exam".
        details: The body text explaining the request (dates, reason) as given by the student.
        student_name: Student's name if the student provided it; leave empty otherwise.
        roll_number: Student's roll number if provided; leave empty otherwise.

    Returns:
        dict with the draft text and the file path where it was saved.
    """
    def blank(v):
        return v is None or str(v).strip().lower() in ("", "none", "null", "n/a")

    if blank(to_email) or "@" not in str(to_email):
        return {"saved": False, "sent": False,
                "error": "No valid recipient email address. Call get_instructor_email first and pass the "
                         "email it returns as to_email. If no email is found, tell the student you do not know "
                         "the instructor instead of drafting."}
    instructor_name = "" if blank(instructor_name) else str(instructor_name)
    student_name = "" if blank(student_name) else str(student_name)
    roll_number = "" if blank(roll_number) else str(roll_number)
    name = student_name.strip() or "[Your Name]"
    roll = roll_number.strip() or "[Your Roll Number]"
    subject = f"{course_code}: {purpose}".strip(": ")
    body = (f"To: {to_email or '[Instructor Email]'}\n"
            f"Subject: {subject}\n\n"
            f"Dear {instructor_name or 'Sir/Madam'},\n\n"
            f"{details.strip()}\n\n"
            f"Thank you for your consideration.\n\n"
            f"Sincerely,\n{name}\nRoll No.: {roll}\n")
    EMAIL_DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = EMAIL_DRAFT_DIR / f"{stamp}_{re.sub(r'[^A-Za-z0-9]+', '_', course_code or 'course')}.txt"
    path.write_text(body, encoding="utf-8")
    return {"saved_to": str(path), "sent": False, "draft": body}


def log_unanswered(question: str, reason: str) -> dict:
    """Record a question the helpdesk cannot answer so a human can follow up.
    Call this whenever the answer is not in the documents/tools or the question is
    outside the academic scope.

    Args:
        question: The user's question, verbatim.
        reason: Why it could not be answered, e.g. "out of scope" or "not in documents".

    Returns:
        dict confirming the entry was logged.
    """
    UNANSWERED_LOG.parent.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now()
    # skip duplicates: the agent tool call and the refusal callback can both log the same reply
    if UNANSWERED_LOG.exists():
        for line in UNANSWERED_LOG.read_text(encoding="utf-8").splitlines()[-50:]:
            prev = json.loads(line)
            if prev["question"].strip() == question.strip() and \
                    now - dt.datetime.fromisoformat(prev["timestamp"]) < dt.timedelta(minutes=2):
                return {"logged": True, "note": "already logged"}
    entry = {"timestamp": now.isoformat(timespec="seconds"), "question": question, "reason": reason}
    with open(UNANSWERED_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"logged": True}
