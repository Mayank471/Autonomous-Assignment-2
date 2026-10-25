"""Build eval/review/question_answer_sheet.xlsx: the question set with reference answers, the exact
evidence quoted from the source pages, and links, for a human to verify.

Sheets:
  Read me                    how to use the sheet
  1 Verify Q&A              one row per question: reference answer + evidence + source + verdict dropdown
  2 System answers          (optional) every system answer with the automatic and reviewed grade

The evidence text is cut from the extracted document text (data/text/*.json) or from the scraped tables
(data/structured/*.csv). While building, every reference answer's key facts are checked against its
evidence; failures are printed so that nothing unsupported reaches the sheet silently.

Usage: python eval/build_review_sheet.py
"""
import csv
import json
import re
import sys
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval" / "review" / "question_answer_sheet.xlsx"


def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


QUESTIONS = read_csv(ROOT / "eval" / "questions.csv")
SOURCES = {r["doc_id"]: r for r in read_csv(ROOT / "data" / "sources.csv") if r["status"] == "ok"}
CATALOGUE = read_csv(ROOT / "data" / "structured" / "catalogue.csv")
COURSES = read_csv(ROOT / "data" / "structured" / "courses.csv")
SLOTS = read_csv(ROOT / "data" / "structured" / "slots.csv")
FACULTY = read_csv(ROOT / "data" / "structured" / "faculty.csv")
TEACHING = read_csv(ROOT / "data" / "structured" / "teaching.csv")

_pages = {}


def pages(doc):
    if doc not in _pages:
        p = ROOT / "data" / "text" / f"{doc}.json"
        _pages[doc] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    return _pages[doc]


def page_text(doc, page):
    for p in pages(doc):
        if p["page"] == page:
            return norm(p["text"]), p["method"]
    return "", ""


def window(text, anchor, before=200, after=330):
    i = text.lower().find(anchor.lower())
    if i < 0:
        return None
    a, b = max(0, i - before), min(len(text), i + len(anchor) + after)
    return ("… " if a else "") + text[a:b] + (" …" if b < len(text) else "")


def facts_ok(key_facts, text):
    """Same rule as eval/score.py: every ';' fact needs one of its '|' alternatives in the text."""
    t = norm(text).lower().replace("–", "-")
    for fact in filter(None, (f.strip() for f in key_facts.split(";"))):
        found = False
        for alt in filter(None, (a.strip().lower() for a in fact.split("|"))):
            pat = (r"(?<![\w@.])" + re.escape(alt) + r"(?![\w@])") if len(alt) <= 3 else re.escape(alt)
            if re.search(pat, t):
                found = True
                break
        if not found:
            return False
    return True


def pretty_facts(kf):
    if not kf:
        return "—"
    return "  AND  ".join(" or ".join(a.strip() for a in f.split("|")) for f in kf.split(";") if f.strip())


def src_line(doc, page=None):
    s = SOURCES[doc]
    where = f", p.{page}" if page else ""
    tag = " [campus network only]" if s["access"] == "campus-network" else ""
    return f"{doc}: {s['title']}{where}{tag}"


# anchors that locate the relevant sentence/row when the key fact alone is too generic (e.g. "10", "7")
ANCHORS = {
    ("P02", "D01"): "Electives (OE)", ("P02", "D16"): "12 credits of open elective", ("P02", "D20"): "Electives (OE)",
    ("P10", "D01"): "B- 7", ("P10", "D05"): "B- 7",
    ("P11", "D01"): "Minimum for Continuation",
    ("P12", "D16"): "requires a total of 153 credits",
    ("P15", "D01"): "Lecture courses", ("P15", "D05"): "Lecture courses",
    ("P13", "D22"): "CSL7650",
}


# judgement calls the automatic key-fact check cannot settle: shown to the human reviewer
EXTRA_NOTES = {
    "P01": "PLEASE JUDGE: the circular says attendance 'should not fall below 75%' but ALSO that exam performance is 'no longer "
           "linked to attendance' and students may still appear. Strictly, there may be NO attendance requirement to sit the exam. "
           "The scorer only checks that '75%' is mentioned, so an answer saying 'you need 75% to sit the exam' passes. "
           "Should the reference answer say this explicitly?",
    "P08": "PLEASE CHECK: the calendar row is labelled 'MAJOR Examination (Fractal 3 and M.Tech. working professional)'. "
           "Do these dates apply to the Major exam of ALL Semester I courses, or only to those groups?",
    "P13": "Two courses share the name in the ERP catalogue: CSL7650 (CSE, 700-level) and RML6020 (Robotics & Mobility Systems, "
           "600-level). Answers naming both are accepted.",
}


def row_text(r, keys):
    return " | ".join(f"{k}: {r[k]}" for k in keys if r.get(k))


def custom_evidence(qid):
    """Evidence for questions answered from scraped tables (or by absence). Returns (evidence, sources, local, link, note)."""
    ev, srcs, loc = [], [], []
    note = ""
    if qid in ("S03", "E04"):
        r = next(x for x in COURSES if x["course_code"] == "CSL1010")
        ev.append("courses.csv row (from the 'Courses As per Curriculum' sheet of D15): " +
                  row_text(r, ["course_code", "course_name", "offered_to", "credits", "ltp", "instructor", "instructor_email", "slot", "room", "semester"]))
        srcs, loc = [src_line("D15")], ["data/raw/D15.xlsx → sheet 'Courses As per Curriculum'"]
    elif qid == "S04":
        rows = [x for x in SLOTS if x["slot"] == "G"]
        ev.append("slots.csv rows for slot G (from the 'UG 1st Year Slots' sheet of D15):\n" +
                  "\n".join(row_text(r, ["slot", "day", "time", "cell_text", "semester"]) for r in rows))
        srcs, loc = [src_line("D15")], ["data/raw/D15.xlsx → sheet 'UG 1st Year Slots'"]
    elif qid == "S06":
        for p in pages("D15"):
            w = window(norm(p["text"]), "Kshitiz Gajjar", 160, 120)
            if w:
                ev.append(f"D15, sheet {p['page']}: {w}")
                break
        srcs, loc = [src_line("D15")], ["data/raw/D15.xlsx → sheet 'Faculty Advisors'"]
    elif qid == "S07":
        r = next(x for x in CATALOGUE if x["course_code"] == "CSL7570")
        ev.append(f"catalogue.csv row (ERP course catalogue, department CS): {r['course_code']} | {r['course_title']} | "
                  f"L-T-P: {r['L']}-{r['T']}-{r['P']} | credits: {r['credits']}")
        srcs, loc = [src_line("D29")], ["data/raw/D29_erp/CS.html"]
    elif qid == "S08":
        for r in TEACHING:
            if r["course_code"] == "CSL7650":
                ev.append(f"teaching.csv row (page {r['source_url']}): \"{r['context']}\" → instructor {r['instructor']}, AY {r['academic_year']} Sem {r['semester']}")
        srcs, loc = [src_line("D30")], ["data/raw/D30_teaching/ (see index.csv for the page)"]
    elif qid == "E01":
        c = next(x for x in CATALOGUE if x["course_code"] == "CSL7570")
        ev.append(f"Catalogue (D29): {c['course_code']} = {c['course_title']}")
        for r in TEACHING:
            if r["course_code"] == "CSL7570":
                ev.append(f"Faculty page (D30, {r['source_url']}): \"{r['context']}\"")
        f = next(x for x in FACULTY if x["name"] == "Rajendra Nagar")
        ev.append(f"People directory (D28): {f['name']}, {f['designation']}, {f['department']}, email {f['email']}")
        srcs = [src_line("D29"), src_line("D30"), src_line("D28-electrical-engineering")]
        loc = ["data/raw/D29_erp/CS.html", "data/raw/D30_teaching/", "data/raw/D28_electrical-engineering.html"]
        note = "Instructor shown is the MOST RECENT LISTED offering (AY 2024-25 Sem I), not necessarily this semester's."
    elif qid == "E02":
        for r in [x for x in COURSES if x["course_code"] == "MAL1010"]:
            ev.append("courses.csv row (D15): " + row_text(r, ["course_code", "course_name", "offered_to", "instructor", "instructor_email", "slot", "semester"]))
        srcs, loc = [src_line("D15")], ["data/raw/D15.xlsx → sheet 'Courses As per Curriculum'"]
    elif qid == "E03":
        r = next(x for x in COURSES if x["course_code"] == "PHL1010")
        ev.append("courses.csv row (D15): " + row_text(r, ["course_code", "course_name", "instructor", "instructor_email", "semester"]))
        srcs, loc = [src_line("D15")], ["data/raw/D15.xlsx → sheet 'Courses As per Curriculum'"]
    elif qid == "E05":
        r = next(x for x in FACULTY if x["name"] == "Anand Mishra")
        ev.append("faculty.csv row (People directory, CSE): " + row_text(r, ["name", "designation", "department", "email", "profile_url"]))
        srcs, loc = [src_line("D28-computer-science-engineering")], ["data/raw/D28_computer-science-engineering.html"]
    elif qid == "S01":
        cs = [x for x in CATALOGUE if x["course_title"].lower() == "autonomous systems"]
        ev.append("Catalogue (D29): " + "; ".join(f"{x['course_code']} {x['course_title']} (dept {x['erp_department']}, L-T-P {x['L']}-{x['T']}-{x['P']}, {x['credits']} credits)" for x in cs))
        ev.append("Offerings found on faculty pages (D30): " + "; ".join(f"{r['course_code']}: {r['context']} → {r['instructor']}" for r in TEACHING if r["course_code"] == "CSL7650"))
        ev.append(f"Slot data: the only published course timetable is D15 (AY 2023-24 Sem I, 1st year): {len(COURSES)} courses, none of them Autonomous Systems. "
                  f"No slot for AY 2026-27 Sem I exists in any scraped source.")
        srcs = [src_line("D29"), src_line("D30"), src_line("D15")]
        loc = ["data/raw/D29_erp/", "data/raw/D30_teaching/", "data/raw/D15.xlsx"]
        note = "A correct answer says the slot is NOT available. Giving any slot is wrong."
    elif qid == "S02":
        hs = [x for x in CATALOGUE if x["dept_code"] == "HS" and x["level"] == "400"]
        cur = [r for r in TEACHING if r["academic_year"] == "2026-27"]
        ev.append(f"Catalogue (D29): {len(hs)} approved HS 400-level courses (approved, NOT necessarily floated this semester), e.g. " + ", ".join(x["course_code"] for x in hs[:6]) + " …")
        ev.append(f"Faculty pages (D30) list {len(cur)} offerings for AY 2026-27 ({', '.join(sorted({r['course_code'] for r in cur}))}); none is an HS course. "
                  "So 0 is only a lower bound.")
        ev.append("No official list of courses floated in AY 2026-27 Sem I exists in any scraped source.")
        srcs = [src_line("D29"), src_line("D30"), src_line("D11", 1)]
        loc = ["data/raw/D29_erp/HS.html", "data/raw/D30_teaching/", "data/raw/D11.pdf (semester dates, p.1)"]
        note = "A correct answer says the count is unavailable/incomplete. Presenting '0' as the official number without that caveat is wrong."
    return ev, srcs, loc, note


OOS_KEYWORDS = {
    "O01": [r"\bdining\b", r"\bmess\b", r"\bcanteen\b", r"\bcafeteria\b", r"food court"],
    "O02": [r"railway", r"airport", r"bus (stand|station|stop)", r"\btaxi\b", r"city cent(er|re)", r"how to reach"],
    "O03": [r"\bplacements?\b", r"\bpackage\b", r"\bsalary\b", r"\bCTC\b"],
    "O04": [r"\bwi-?fi\b", r"\bwifi\b", r"\bVPN\b", r"\binternet access\b"],
}


def oos_evidence(qid):
    hits = []
    for p in sorted((ROOT / "data" / "text").glob("*.json")):
        for pg in json.loads(p.read_text(encoding="utf-8")):
            t = norm(pg["text"])
            for pat in OOS_KEYWORDS[qid]:
                m = re.search(pat, t, re.I)
                if m:
                    hits.append((p.stem, pg["page"], pat, t[max(0, m.start() - 60):m.end() + 60]))
    total_pages = sum(len(pages(p.stem)) for p in (ROOT / "data" / "text").glob("*.json"))
    ev = f"Keyword scan of all {total_pages} indexed pages for {', '.join(OOS_KEYWORDS[qid])}: {len(hits)} matching page(s)."
    for d, pg, pat, ctx in hits[:4]:
        ev += f"\n  {d} p.{pg}: …{ctx}…"
    if hits:
        ev += "\n  (these are course-content / unrelated contexts, none describes a campus service)"
    return ev


def build_sheet1(wb):
    ws = wb.create_sheet("1 Verify Q&A")
    headers = ["ID", "Category", "Expected behaviour", "Question", "Reference answer (what a correct system says)",
               "Key facts the scorer requires", "Evidence quoted from the source (verbatim)",
               "Source document(s)", "Page / location in the file", "Link (first source)",
               "YOUR VERDICT", "Your correction / comment"]
    ws.append(headers)
    behaviour = {"answer": "Answer with citation", "draft": "Draft an email (not sent)",
                 "no_data": "Say the data is NOT published (no guessing)", "refuse": "Refuse: 'I don't know' + log"}
    problems = []
    for q in QUESTIONS:
        qid = q["id"]
        ev, srcs, locs, note = [], [], [], ""
        link = ""
        if qid in OOS_KEYWORDS:
            ev = [oos_evidence(qid)]
            srcs = ["(none: out of scope)"]
            locs = ["data/text/*.json (all indexed pages)"]
            if qid == "O02":
                note = "The institute website has a general 'How to reach' page, but it is deliberately NOT in the corpus: the assignment defines this question as one the agent must not answer."
        elif q["sources"] and any(re.match(r"^D\d+[A-Za-z]?:\d+$", s) for s in q["sources"].split("|")):
            used = 0
            for spec in q["sources"].split("|"):
                doc, _, pg = spec.partition(":")
                if not pg:  # table-based source mixed with page-based ones (P13: ERP catalogue)
                    cat = [x for x in CATALOGUE if x["course_title"].lower() == "autonomous systems"]
                    ev.append("[D29, ERP course catalogue] " + "; ".join(
                        f"{x['course_code']} {x['course_title']} (L-T-P {x['L']}-{x['T']}-{x['P']}, {x['credits']} credits)" for x in cat))
                    srcs.append(src_line(doc))
                    locs.append("data/raw/D29_erp/CS.html")
                    continue
                text, method = page_text(doc, int(pg))
                anchor = ANCHORS.get((qid, doc))
                if not anchor:
                    alts = sorted({a.strip() for f in q["key_facts"].split(";") for a in f.split("|") if a.strip()}, key=len, reverse=True)
                    anchor = next((a for a in alts if a.lower() in text.lower().replace("–", "-")), None)
                w = window(text, anchor) if anchor else None
                if w and used < 3:
                    scan = " (scanned page, text recognised by OCR)" if method == "ocr" else ""
                    ev.append(f"[{doc}, p.{pg}]{scan} {w}")
                    srcs.append(src_line(doc, int(pg)))
                    locs.append(f"{SOURCES[doc]['local_file']} → PDF page {pg}")
                    used += 1
            if not ev:
                problems.append((qid, "anchor not found in any cited page"))
        else:
            ev, srcs, locs, note = custom_evidence(qid)
            if not ev:
                problems.append((qid, "no evidence built"))
        # validation of the reference answer against its evidence
        if q["key_facts"] and ev and not facts_ok(q["key_facts"], " ".join(ev)):
            problems.append((qid, "key facts NOT all found in the quoted evidence"))
        first_doc = re.match(r"^\s*([A-Za-z0-9\-]+)", srcs[0]).group(1) if srcs and srcs[0].startswith("D") else None
        link = SOURCES[first_doc]["url"] if first_doc in SOURCES else ""
        note = " ".join(filter(None, [note, EXTRA_NOTES.get(qid, "")]))
        answer = q["expected_answer"] + (f"\n\nNOTE: {note}" if note else "")
        if q["notes"]:
            answer += f"\n\n(Author's note: {q['notes']})"
        ws.append([qid, q["category"], behaviour[q["expected_behavior"]], q["question"], answer,
                   pretty_facts(q["key_facts"]), "\n\n".join(ev), "\n".join(srcs), "\n".join(locs), link, None, None])
        if link:
            c = ws.cell(row=ws.max_row, column=10)
            c.hyperlink = link
            c.font = Font(color="0563C1", underline="single")
    # layout
    widths = [6, 12, 20, 38, 52, 26, 80, 44, 36, 30, 16, 36]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    style_header(ws, len(headers), highlight_cols=(11, 12))
    body_style(ws, highlight_cols=(11, 12))
    dv = DataValidation(type="list", formula1='"Correct,Wrong,Unsure"', allow_blank=True)
    dv.error, dv.errorTitle, dv.showErrorMessage = "Choose Correct, Wrong or Unsure", "Verdict", True
    ws.add_data_validation(dv)
    dv.add(f"K2:K{ws.max_row}")
    ws.freeze_panes = "E2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{ws.max_row}"
    return problems


def build_sheet2(wb):
    ws = wb.create_sheet("2 System answers (optional)")
    headers = ["ID", "Question", "System", "Run", "Answered by", "Tools used", "System answer (text before 'Sources')",
               "Sources cited by the system", "Automatic grade", "Reviewed grade (mine)", "Why (my note)",
               "YOUR VERDICT on my grade", "Your comment"]
    ws.append(headers)
    qtext = {q["id"]: q["question"] for q in QUESTIONS}
    order = {q["id"]: i for i, q in enumerate(QUESTIONS)}
    runs = [("Qwen3 8B single agent", "qwen3-8b", "single"), ("Qwen3 8B multi-agent", "qwen3-8b", "multi"),
            ("Llama 3.1 8B multi-agent", "llama31-8b", "multi")]
    rows = []
    for label, tag, sysn in runs:
        grades = {(g["system"], g["run"], g["id"]): g for g in read_csv(ROOT / "eval" / "results" / f"grades_{tag}.csv")}
        for line in open(ROOT / "eval" / "results" / f"{sysn}_{tag}.jsonl", encoding="utf-8"):
            r = json.loads(line)
            g = grades.get((sysn, str(r["run"]), r["id"]))
            if not g:
                continue
            ans = (r.get("answer") or "").strip()
            body, _, srcs = ans.partition("Sources")
            tools = ", ".join(c["name"] for c in r["tool_calls"] if c["name"] != "transfer_to_agent") or "none"
            note = re.sub(r"\s*\[reviewer:.*?\]\s*$", "", g["reviewer_note"])
            rows.append((order[r["id"]], label, r["run"], [r["id"], qtext[r["id"]], label, r["run"], r["answered_by"], tools,
                         body.strip()[:1500], ("Sources" + srcs).strip()[:600] if srcs else "—",
                         "correct" if g["auto_correct"] == "1" else "wrong",
                         "correct" if g["manual_correct"] == "1" else "wrong", note, None, None]))
    for _, _, _, row in sorted(rows, key=lambda x: (x[0], x[1], x[2])):
        ws.append(row)
    for i, w in enumerate([6, 34, 22, 5, 18, 26, 70, 40, 11, 12, 44, 16, 30], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    style_header(ws, len(headers), highlight_cols=(12, 13))
    body_style(ws, highlight_cols=(12, 13))
    red = PatternFill("solid", fgColor="FDE9E7")
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 10).value == "wrong":
            ws.cell(r, 10).fill = red
    dv = DataValidation(type="list", formula1='"Agree,Disagree,Unsure"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"L2:L{ws.max_row}")
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{ws.max_row}"
    return len(rows)


thin = Side(style="thin", color="BBBBBB")


def style_header(ws, n, highlight_cols=()):
    for c in range(1, n + 1):
        cell = ws.cell(1, c)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="C55A11" if c in highlight_cols else "1F3864")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[1].height = 34


def body_style(ws, highlight_cols=()):
    yellow = PatternFill("solid", fgColor="FFF8DC")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
            if cell.column in highlight_cols:
                cell.fill = yellow


def build_readme(wb):
    ws = wb.active
    ws.title = "Read me"
    lines = [
        ("How to verify this sheet", True),
        ("", False),
        ("Sheet '1 Verify Q&A' (the one that matters): 30 questions. For each row, read the reference answer, then check the quoted", False),
        ("evidence against the real source (open the link, or the local file at the PDF page given). Choose Correct / Wrong / Unsure in the", False),
        ("orange 'YOUR VERDICT' column and write the right answer in the last column if it is wrong.", False),
        ("", False),
        ("Things to know while checking:", True),
        ("• Page numbers are PDF page positions (1 = first page of the file), NOT necessarily the number printed on the page.", False),
        ("• 'Scanned page' evidence comes from OCR, so look at the picture, not only at the text.", False),
        ("• Rows marked 'Say the data is NOT published' (S01, S02) have no right numeric answer: the official data does not exist publicly.", False),
        ("• Several questions have answers that depend on the batch/regulation year (e.g. P02: 10 credits in the 2019 regulations, 12 in the 2026 curriculum).", False),
        ("• Links marked [campus network only] open only from the IIT Jodhpur network; use the local file path instead.", False),
        ("• Answers marked 'most recent listed offering' (E01) come from faculty web pages, not from an official timetable.", False),
        ("", False),
        ("Sheet '2 System answers (optional)': all 270 answers the three systems gave, with the automatic grade and my reviewed grade.", False),
        ("Use it only if you also want to check my grading (orange columns). Rows where my grade is 'wrong' are shaded.", False),
        ("", False),
        ("When you are done, save the file and tell me: I will copy your verdicts into eval/questions.csv (the 'verified' column),", False),
        ("fix any reference answer you marked Wrong, and re-score.", False),
    ]
    for i, (text, bold) in enumerate(lines, 1):
        c = ws.cell(i, 1, text)
        c.font = Font(bold=bold, size=14 if i == 1 else 11)
    ws.column_dimensions["A"].width = 150


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    build_readme(wb)
    problems = build_sheet1(wb)
    n = build_sheet2(wb)
    wb.save(OUT)
    print(f"saved {OUT} (sheet 1: {len(QUESTIONS)} questions, sheet 2: {n} system answers)")
    print("VALIDATION PROBLEMS:", problems or "none: every reference answer is supported by its quoted evidence")


if __name__ == "__main__":
    main()
