# Autonomous Assignment 2: IIT Jodhpur Academic Helpdesk

A local, multi-agent academic helpdesk for IIT Jodhpur students, built with **Google ADK**, **Ollama** (Qwen3 8B / Llama 3.1 8B, `nomic-embed-text`) and **ChromaDB**. It answers questions about regulations, curricula, course contents, the academic calendar and timetable data; drafts (never sends) emails to instructors; cites the document behind every answer; and says "I don't know" (and logs the question) when it has no grounded answer.

*Course:* Autonomous Systems, Assignment 2 ("Academic Helpdesk Agent").

## Contents

1. [Overview and deliverables](#1-overview-and-deliverables)
2. [Quick start](#2-quick-start)
3. [How the system works](#3-how-the-system-works)
4. [Evaluation](#4-evaluation)
5. [Data](#5-data)
6. [Limitations](#6-limitations)
7. [Repository layout](#7-repository-layout)
8. [Environment notes](#8-environment-notes)

---

## 1. Overview and deliverables

| Assignment requirement | Where |
|---|---|
| Single-agent version: RAG pipeline + all tools | `agents/single_agent`, `helpdesk/` |
| Multi-agent version: orchestrator routing to a policy agent, a schedule agent and an email agent | `agents/multi_agent`, `helpdesk/agents.py` |
| RAG with a local embedding model and ChromaDB (OCR for scanned PDFs, page-bounded chunks, hybrid dense + BM25 retrieval) | `scripts/ingest.py`, `helpdesk/tools.py` |
| Tools: `search_documents`, `lookup_course`, `list_courses`, `get_slot_timings`, `get_instructor_email`, `draft_email` (saved for review, never sent), `log_unanswered` | `helpdesk/tools.py` |
| Refuse out-of-scope questions instead of guessing, and log them for a human | `logs/unanswered.jsonl` (a real sample from the evaluation runs) |
| Answers cite the source document (title, page, URL) | prompts in `helpdesk/prompts.py` |
| 20-30 real documents (regulations, circulars, timetable, calendars, office orders, faculty emails) | 27 documents + People directory + ERP catalogue + faculty pages; registered in `data/sources.csv` |
| Question set (30 questions, all 7 examples from the assignment) | `eval/questions.csv` |
| Evaluation: accuracy, groundedness, correct refusals, LLM replacement, answers that changed between runs | `eval/`, `eval/results/`, section 4 |
| Report with the findings | `REPORT.pdf` (built from `REPORT.md`), `REPORT.md`, `report/report.tex` |
| Runs on a 16 GB laptop | measured, see below |

**Memory.** Peak memory was measured on this 15.7 GB laptop while the 7 example questions of the assignment ran through the multi-agent system (`powershell -File eval\measure_ram.ps1 -Command "python eval\smoke_test.py"`, samples in `eval/results/ram_samples.csv`, 2026-10-30). The Qwen3 8B chat model and the embedding model in Ollama peaked at **5.8 GB** and the Python process (agents, ChromaDB, BM25) at **0.4 GB**, about **6.2 GB** for the whole system; the machine as a whole peaked at 14.2 GB of 15.7 GB, including the operating system and the other applications that were open (7.7 GB in use before the run).

**Reference answers.** Every expected answer in `eval/questions.csv` is quoted from an official IIT Jodhpur document (`doc:page` given), and the official document is taken as the truth. Two rulings were needed:

* **P01** (*attendance requirement to sit the Major exam*): the circular of 08-07-2024 (D08) states that examination performance "is no longer linked to their course attendance" and that it supersedes the earlier policy "in totality". So there is **no attendance requirement to sit the exam**; students are expected to attend fully and attendance "should not fall below 75%", otherwise the instructor may recommend de-registration. An answer that makes 75% a condition for sitting the exam, or presents the old rule (below 75% must score at least a C) as current, is graded wrong.
* **P08** (*Major exam, Semester I 2026-27*): the detailed schedule of the Academic Calendar AY 2026-27 (D11 p.8, row 79) lists "Major Semester Examination, 19-26 Nov 2026" for Semester I, so the reference is 19-26 November 2026.

`python eval/check_sources.py` checks that the key facts of every answerable reference occur on the cited source page (21 of 22 do; the 22nd, S07, matches the ERP catalogue row, where L-T-P and credits sit in separate columns). The `verified` column of `eval/questions.csv` records this. It shows that the references agree with the sources; it is not an independent human review, and the answers were graded by reading them against the references.

---

## 2. Quick start

Prerequisites: Windows 11 (Linux/macOS should work), Python 3.13, [Ollama](https://ollama.com), 16 GB RAM. A GPU is optional but makes the run ~10x faster (development used an RTX 3050 with 4 GB). Tesseract OCR is needed only to *re-extract* the scanned PDFs; the extracted text is committed in `data/text/`.

```bash
# 1. models (Ollama must be running)
ollama pull qwen3:8b
ollama pull nomic-embed-text
ollama create qwen3-8b-helpdesk -f ollama/Modelfile          # same model with an 8K context window
# optional, for the model comparison
ollama pull llama3.1:8b
ollama create llama31-8b-helpdesk -f ollama/Modelfile.llama31

# 2. Python environment
python -m venv .venv
.venv\Scripts\activate                                        # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# 3. build the search index from the committed data (a few minutes; needs Ollama)
python scripts/ingest.py

# 4. use it
adk web agents                                                # browser UI; pick multi_agent or single_agent
python -m helpdesk.runner --system multi "What is the attendance requirement to sit in the Major exam?"
python eval/smoke_test.py                                     # the 7 example questions from the assignment, 5-10 minutes
```

`data/chroma/` (the vector index) is not committed; step 3 creates it. Email drafts are written to `outputs/email_drafts/`, unanswered questions to `logs/unanswered.jsonl`.

Settings come from environment variables (see `.env.example`): `OLLAMA_API_BASE`, `HELPDESK_LLM`, `HELPDESK_EMBED`, `HELPDESK_THINK` (1 = let Qwen3 think; much slower).

**Example, as produced by the multi-agent version** (`Write an email to the course instructor of CSL7570 that I need leave for 2 days`):

```text
To: rn@iitj.ac.in
Subject: CSL7570: Sick leave for 2 days

Dear Rajendra Nagar,

I need to take leave for 2 days due to [reason]. The dates of my leave are [dates].

Thank you for your consideration.

Sincerely,
[Your Name]
Roll No.: [Your Roll Number]
```

The instructor is the most recent one listed on a faculty web page (AY 2024-25 Semester I); the answer says so, and the student's name, reason and dates stay as placeholders because they were not given.


---

## 3. How the system works

```text
student ─▶ helpdesk_orchestrator ── out of scope ──▶ "I don't know" + log_unanswered
                │ transfer_to_agent
     ┌──────────┼───────────────────────┐
     ▼          ▼                       ▼
policy_agent  schedule_agent          email_agent
search_docs   lookup_course           get_instructor_email
              list_courses            lookup_course
              get_slot_timings        draft_email ─▶ outputs/email_drafts/
              get_instructor_email
              search_docs
```

* **Single agent** (`agents/single_agent`): one ADK `LlmAgent` with all seven tools. **Multi-agent** (`agents/multi_agent`): the orchestrator has only `log_unanswered` and routes with ADK's `transfer_to_agent`; specialists cannot transfer back or sideways. Models are called through ADK's LiteLLM connector (`ollama_chat/` provider; do not use the plain `ollama/` provider, it loops on tool calls).
* **Prompts** are in `helpdesk/prompts.py` (grounding rules, scope definition, email rules). **Agent builders** are in `helpdesk/agents.py`; `helpdesk/runner.py` runs an agent programmatically and records tool calls, answering agent and latency.

| Tool | Data | What it does |
|---|---|---|
| `search_documents` | 586 chunks in ChromaDB + BM25 | Hybrid retrieval (dense top-30 and BM25 top-30 merged by reciprocal-rank fusion, top 5 returned) with title, page and URL for citation |
| `lookup_course` | `catalogue.csv`, `teaching.csv`, `courses.csv` | Code or name → official catalogue entry (L-T-P, credits), offering history (semester, instructor), and the published slot if any |
| `list_courses` | same | Counts courses by department, level and type using the course-code scheme of the Regulations (D01 pp.4-5). Counts either the whole catalogue or only the courses listed as offered in the current semester, and returns the basis of the count |
| `get_slot_timings` | `slots.csv` | Slot → days and times |
| `get_instructor_email` | `courses.csv`, `teaching.csv`, `faculty.csv` | Instructor and email by course code or faculty name, with the semester the information refers to |
| `draft_email` | none | Saves a draft for the student to review. Never sends. Refuses to save a draft without a valid recipient address |
| `log_unanswered` | `logs/unanswered.jsonl` | Appends the question for a human to follow up |

**RAG details.** PyMuPDF extracts text page by page; pages with no text layer (two circulars, two office orders) are OCR'd with Tesseract. Chunks are ~450 words with an 80-word overlap and never cross a page boundary, so every chunk has an exact page for citation. Embeddings use `nomic-embed-text` with its task prefixes and the document title prepended. Retrieval is capped at 5 passages: on a 4 GB GPU generation slows from 6.6 to 2.8 tokens/s as the context grows from 1K to 5K tokens.

**Guardrails** (`helpdesk/callbacks.py`, ADK `after_model_callback`):

* *Tool-first guards.* If a model tries to give a final answer without having called any tool in that turn, the answer is replaced by a forced tool call (`search_documents`, or `get_instructor_email` for the email agent). Specialist agents use a *strict* variant that also forbids refusing before trying a tool, because the orchestrator has already judged the question in scope. The single agent may refuse directly. This was the most effective change: it took accuracy from 52% to 74% and removed fabricated citations (section 4.2).
* *Refusal logging.* Every reply starting with "I don't know" is written to the unanswered log even if the model forgot to call `log_unanswered`; duplicates within two minutes are dropped.
* The grounding prompt: answer only from tool output; cite as *title, p.N, url*; never write a URL that did not come from a tool; a circular that amends a regulation overrides it; always say which semester slot, instructor or count data refers to; never guess a slot.

---

## 4. Evaluation

### 4.1 Question set and method

`eval/questions.csv` (generated by `eval/build_questions.py`) has **30 questions**: 14 policy, 7 schedule, 5 email, 4 out of scope. It contains all seven examples from the assignment. Every expected answer is a verbatim quote from a collected source with its acceptable `doc:page` citations. Out-of-scope questions were checked against the corpus (a keyword scan finds no document describing dining, getting to campus, placement packages or campus Wi-Fi).

Each question is asked in a fresh ADK session, **3 times** per system, at default sampling (temperature 0.6). Systems: Qwen3 8B single agent, Qwen3 8B multi-agent, Llama 3.1 8B multi-agent. Metrics (`eval/score.py`, rule-based; no LLM judge):

* *accuracy:* every key fact present and not a refusal; for "data not published" items, the answer must say so and invent nothing; for out-of-scope items, the answer must refuse **and** the question must be logged;
* *groundedness:* the cited document, and the document with page, match an expected source;
* *retrieval hit, fabricated URL, routing accuracy, run-to-run consistency* (which questions' outcome changed between runs).

Every in-scope answer was then read against its expected answer (`eval/results/grades_*.csv`, 17 automatic grades overridden, reasons in `eval/apply_manual_grades.py`). The scores were recomputed on 2026-10-30 after ruling on P01 (see section 1); no model was re-run for that.

### 4.2 Results (3 runs × 30 questions, answers read against the references)

| | Qwen3 single | **Qwen3 multi-agent** | Llama 3.1 multi-agent |
|---|---|---|---|
| Accuracy on answerable questions | 58% (42/72) | **79% (57/72)** | 50% (36/72) |
| Cited document is a correct source | 64% | **83%** | 64% |
| Cited document and page correct | 58% | **76%** | 54% |
| Out-of-scope refused and logged | 12/12 | 12/12 | 12/12 |
| "Data not published" handled correctly | 4/6 | **6/6** | 6/6 |
| False refusals on answerable questions | 28% | **8%** | 12% |
| Answers with a fabricated URL | 0% | 0% | 1% |
| Routing accuracy | none | 87% | 88% |
| Questions whose outcome changed between runs | 10 | **2** | 17 |
| Median latency | 33 s | 40 s | 30 s |

Findings (full discussion, error analysis and the list of questions whose answers changed are in [REPORT.md](REPORT.md)): the multi-agent version beats the single agent by 21 points; tool-first guards removed the fabricated citations of the first version (52% accuracy, 17% fabricated URLs); swapping the LLM cost 29 points (Llama ignores tool results, e.g. it says it cannot find an email the tool just returned). Wrong in every run of the best system: P01 (answers make 75% a condition for the exam instead of saying there is none), P08 (Major exam dates, table misread), P15 (meaning of the letter "L" in a course code), P17 (Dussehra holiday treated as out of scope), P04 (misrouted).

Raw outputs: `eval/results/{single,multi}_qwen3-8b.jsonl` and `multi_llama31-8b.jsonl` (answers, every tool call with arguments and results, answering agent, latency), `scores_*.csv`, `grades_*.csv`, `summary_*.md`. Files with `v1` / `v2` in the name are earlier iterations of the system, scored on an earlier version of the question set (not comparable one-to-one).

### 4.3 Re-running

```bash
python eval/run_eval.py --system both --runs 3                                   # Qwen3 8B, ~2 h
python eval/run_eval.py --system multi --runs 3 --model ollama_chat/llama31-8b-helpdesk --tag llama31-8b   # ~1 h
python eval/score.py --tag qwen3-8b
python eval/apply_manual_grades.py --tag qwen3-8b
python eval/score.py --tag qwen3-8b                                              # final numbers, using the manual grades
```

**Gotchas.** `run_eval.py` *appends and resumes*: it skips every (system, run, question) already in `eval/results/<system>_<tag>.jsonl`, so re-running with the same tag does nothing. For a fresh run, use a new `--tag` (and pass the same `--tag` to the scoring scripts) or move the old files away. A fresh run produces different answers, so the grade overrides in `apply_manual_grades.py` (tied to the committed answers) no longer apply: read the new answers against the references first.

---

## 5. Data

### 5.1 Sources

Every source is registered in [`data/sources.csv`](data/sources.csv): id, category, title, URL, the page that links to it, access level, local file, download date, SHA-256, size, status, notes. All of it was obtained from IIT Jodhpur web sources; no answer data was typed in by hand. 27 documents plus the People directory (13 pages) are used. The assignment asks for 20-30 real documents covering regulations, timetable, course registration, recent office orders and faculty emails; the corresponding items are the regulations (D01, D04, D05, D10), circulars (D08, D09), calendars with registration dates (D11, D13, D14), the slot timetable (D15), office orders (D32, D33), the fee structure (D34) and the faculty emails (D28).

| ID | Type | Document (link = original URL) | Access | Stored in this repo |
|---|---|---|---|---|
| D01 | regulation | [Academic Regulations - students enrolled from July 2019 onwards](https://iitj.ac.in/PageImages/Gallery/03-2025/1_Academic_Regulations_Final_03_09_2019.pdf) | public | `data/raw/D01.pdf` |
| D04 | regulation | [Notification 26-10-2020: Revised norms for continuation of programme/assistantship and graduation requirements](https://iitj.ac.in/PageImages/Gallery/03-2025/amend_notification_26102020.pdf) | public | `data/raw/D04.pdf` |
| D05 | regulation | [Regulations for Postgraduate Programmes - students enrolled from July 2022 onwards](https://iitj.ac.in/PageImages/Gallery/03-2025/4_Regulation_PG_2022-onwards_20022023.pdf) | public | `data/raw/D05.pdf` |
| D08 | circular | [Circular 08-07-2024: Amendment in the Attendance Policy of the Institute](https://iitj.ac.in/PageImages/Gallery/03-2025/7.1_Circular_51Circular-No.-IITJOAACircular2024-2551682-dated-08-July-2024.pdf) | public | `data/raw/D08.pdf` |
| D09 | circular | [Circular 08-07-2024: Amendment in the Examination Policy of the Institute](https://iitj.ac.in/PageImages/Gallery/03-2025/7.2_Circular_52Circular-No.-IITJOAACircular2024-2552683-dated-08-July-2024.pdf) | public | `data/raw/D09.pdf` |
| D10 | regulation | [B.Tech. Regulations - students who joined in July 2014 and later (rev. 21-07-2018)](https://iitj.ac.in/PageImages/Gallery/04-2025/BTech_Regulations_Latest_21July2018.pdf) | public | `data/raw/D10.pdf` |
| D11 | calendar | [Academic Calendar AY 2026-27](https://iitj.ac.in/PageImages/Gallery/06-2026/Academic-Calendar-AY-2026-27-639178076336417495.pdf) | public | `data/raw/D11.pdf` |
| D13 | calendar | [Academic Calendar for Summer Term 2026](https://iitj.ac.in/PageImages/Gallery/04-2026/Academic-Calendar-for-Summer-Term-2026--639124648616829491.pdf) | public | `data/raw/D13.pdf` |
| D14 | calendar | [Academic Calendar AY 2025-26](https://iitj.ac.in/PageImages/Gallery/07-2025/Academic-Calendar-AY-202526SemI2-with-CCCD-events-638871414539740843.pdf) | public | `data/raw/D14.pdf` |
| D15 | timetable | [Slot System AY 2023-24 Semester-I (B.Tech. 1st Year)](http://academics.iitj.ac.in/wp-content/uploads/2023/08/Slot-System-AY-2023-24-Semester-I-B.Tech_.-1st-Year.xlsx) | campus-network | `data/raw/D15.xlsx` |
| D16 | curriculum | [Detailed curriculum for B.Tech. CSE (AY 2026 onwards)](https://iitj.ac.in/PageImages/Gallery/06-2026/UG-Curriculum-CSE-2026-Onwards-639168740113754926.pdf) | public | `data/raw/D16.pdf` |
| D17 | curriculum | [Detailed curriculum for B.Tech. CSE (before AY 2026)](https://iitj.ac.in/PageImages/Gallery/07-2025/Curriculum-BTech-CSE.pdf) | public | `data/raw/D17.pdf` |
| D18 | course-list | [Details of courses offered by Dept. of CSE](https://iitj.ac.in/PageImages/Gallery/07-2025/CSE-Courses-Details.pdf) | public | `data/raw/D18.pdf` |
| D19 | curriculum | [CSE Specializations and Dual Degree](https://iitj.ac.in/PageImages/Gallery/07-2025/CSE-Specializations-and-DualDegree.pdf) | public | `data/raw/D19.pdf` |
| D20 | curriculum | [Detailed curriculum for B.Tech. AI and Data Engineering (AY 2026 onwards)](https://iitj.ac.in/PageImages/Gallery/06-2026/UG-Curriculum-AIDE-2026-Onwards-639168740417574711.pdf) | public | `data/raw/D20.pdf` |
| D21 | curriculum | [Detailed curriculum for M.Tech. CSE (AY 2025 onwards)](https://iitj.ac.in/PageImages/Gallery/01-2026/Detailed-curriculum-for-MTech-CSE-AY-2025-onwards-639053782130026932.pdf) | public | `data/raw/D21.pdf` |
| D22 | curriculum | [Detailed curriculum for M.Tech. AI (AY 2025 onwards)](https://iitj.ac.in/PageImages/Gallery/01-2026/Detailed-curriculum-for-MTech-AI-AY-2025-onwards-639053782336374627.pdf) | public | `data/raw/D22.pdf` |
| D23 | course-list | [Courses offered by HSS (Concept note 2021, modified 13-01-2022)](https://intranet.iitj.ac.in/acad_website/intra/Final_ConceptNote_HSS_2021%20with%20all%20modifications%20_13.01.2022.pdf) | campus-network | `data/raw/D23.pdf` |
| D24 | course-list | [List of Institute-wide common courses and course contents from 2nd year onwards](https://intranet.iitj.ac.in/acad_website/intra/List%20of%20Institute%20wide%20common%20courses%20and%20course%20contents%20from%202nd%20year%20onwards_31082020.pdf) | campus-network | `data/raw/D24.pdf` |
| D26 | course-list | [Courses identified as programme electives but offered by other departments](https://intranet.iitj.ac.in/acad_website/ug_curriculum/Revised%20courses%20detail%20by%20other%20department_25022021.pdf) | campus-network | `data/raw/D26.pdf` |
| D27 | curriculum | [Minor / Department / Interdisciplinary Specialization](https://intranet.iitj.ac.in/acad_website/Minor_Department_Interdisciplinary%20Specialization_31082020.pdf) | campus-network | `data/raw/D27.pdf` |
| D28-* | faculty-directory | [IIT Jodhpur People directory](https://iitj.ac.in/People) (13 department pages) | public | `data/raw/D28_*.html` |
| D29 | course-catalogue | [Academic ERP course catalogue (all departments)](http://academics.iitj.ac.in:8080/ERP_IITJ/courses.do) | campus-network | `data/raw/D29_erp/` (22 HTML pages) |
| D30 | teaching-history | [Faculty web pages listing courses taught (linked as 'Web Profile' from the People directory)](https://iitj.ac.in/People) | public | only the URL list `data/raw/D30_teaching/index.csv`; derived rows in `data/structured/teaching.csv` |
| D31 | course-list | [School of Liberal Arts - Undergraduate Courses (bouquet courses by semester)](https://iitj.ac.in/school-of-liberal-arts/en/undergraduate-courses) | public | `data/raw/D31.html` |
| D32 | office-order | [Office order IITJ/O(ESTB)/2025-26/1205 (11-12-2025): Institute Holidays Calendar 2026](https://intranet.iitj.ac.in/correspondences/assets/uploads/main_website/Holiday%20Calendar_2026.pdf) | campus-network | `data/raw/D32.pdf` |
| D33 | office-order | [Notification IITJ/REG/2025-26/118 (13-10-2025): Constitution of Course Equivalence and Credit Transfer Committee](https://intranet.iitj.ac.in/correspondences/assets/uploads/main_website/Notification_Constitution%20of%20Course%20Equivalence%20and%20Credit%20Transfer%20Committee_13102025.pdf) | campus-network | `data/raw/D33.pdf` |
| D34 | registration | [Fee structure for AY 2026-27 (regular programmes)](https://iitj.ac.in/PageImages/Gallery/07-2026/Fee-structure-for-AY-2026-27-Regular-639186884218584492.pdf) | public | `data/raw/D34.pdf` |

Duplicates recorded but not ingested (byte-identical copies listed under other names on the website): D02, D03, D04b, D04c.

*Access:* `public` files open from anywhere; `campus-network` files are served from `academics.iitj.ac.in` or `intranet.iitj.ac.in`, which public DNS does not resolve (see 5.5).

### 5.2 Structured tables (`data/structured/`)

Built by `python scripts/build_structured.py` from the raw files. Every row carries `source_doc_id`, which must exist in `data/sources.csv` (the script checks it). Tables whose raw input is not in the repository (`teaching.csv`) are left as committed.

| File | Rows | Columns | Built from |
|---|---|---|---|
| `courses.csv` | 25 | course_code, course_name, offered_to, credits, ltp, instructor, instructor_email, slot, room, semester, source_doc_id | D15 sheet "Courses As per Curriculum" |
| `slots.csv` | 32 | slot, day, time, cell_text, semester, source_doc_id | D15 sheet "UG 1st Year Slots" (merged cells give the 2-hour lab slots) |
| `faculty.csv` | 319 | name, designation, department, email, category, profile_url, source_doc_id | D28-* (Head and all "Faculty" categories; staff are not kept) |
| `catalogue.csv` | 1198 | course_code, course_title, erp_department, dept_code, course_type, level, L, T, P, credits, source_doc_id | D29 ERP course cards |
| `teaching.csv` | 192 | course_code, course_title_on_page, academic_year, semester, semester_label, instructor, instructor_department, instructor_email, context, source_url, source_doc_id | D30 (see 5.3). 101 courses, 20 faculty |

Course codes follow the Regulations (D01 pp.4-5, Tables 4.1-4.3): `<2-letter department><type letter><level digit><2 digits><fractal digit>`, e.g. `CSL7650` = CS department, Lecture course, 700 level. `list_courses` relies on this.


### 5.3 How the data was collected

All files were downloaded from IIT Jodhpur web sources (`iitj.ac.in`, plus `academics.iitj.ac.in` and `intranet.iitj.ac.in`, which resolve only on the campus network). `data/sources.csv` records, for every file, the URL, the page that links to it, the access level, download date, SHA-256 and size. The collection scripts themselves are not part of this repository. Points that matter if the data is refreshed:

* `iitj.ac.in` does not send its intermediate certificate; the operating system's trust store was used (`truststore`), and certificate verification was never disabled.
* Listing pages carry file names with timestamps, so the listing pages (not fixed file URLs) are the stable entry points: `.../office-of-academics/en/academic-regulations`, `.../academic-calendar`, `.../first-year-class-time-table`, the department `undergraduate-programs` pages, and `https://iitj.ac.in/People?dept=<slug>` for the faculty directory.
* The July 2020 and 2021 regulation PDFs are byte-identical to the 2019 one (D02, D03, D04b, D04c are recorded as duplicates and not ingested).
* Scanned PDFs (two circulars, two office orders) are OCR'd with Tesseract by `scripts/ingest.py`.
* Faculty emails come from the People directory (obfuscated as `name[at]iitj[dot]ac[dot]in` and decoded). Course-teaching history (D30) was extracted from faculty web pages; only the extracted course lines and the page URLs are stored (section 5.5).
* On 2026-10-30 the official pages were checked again for newer material: the academic-regulations page lists no document that is missing here that bears on the questions (the 2022 circular on Medical Technologies joint programmes and the M.S. by Research regulations are unrelated), and the Office of Academics still publishes only the first-year timetable of AY 2023-24 as a course-wise timetable.

### 5.4 Known data gaps

* **No current-semester timetable and no list of floated courses** is published on the institute's public site. The system therefore (a) says that no slot is published for any course outside D15 instead of guessing, (b) counts "offered this semester" only from faculty pages and states that the count is a lower bound, and (c) names the *most recent listed* instructor of a course together with the semester of that record (for example CSL7570: Rajendra Nagar, AY 2024-25 Semester I, "with Dr Avinash Sharma"). For the assignment's own examples ("What is the slot for Autonomous Systems?", "How many 400 level electives has the Humanities department floated this semester?") the correct answer with the published data is "not published", and that is what the evaluation expects (S01, S02).
* The only published slot timetable is first-year, AY 2023-24 (25 courses).
* There is no stand-alone "course registration" document; registration is covered by the registration dates in the academic calendars and by the fee structure.
* Assignment examples: CSL7570 = Introduction to Augmented Reality and Virtual Reality (3-0-0, 3 credits); Autonomous Systems = CSL7650 (the ERP catalogue also lists RML6020 with the same title).

### 5.5 Privacy and access

* **Student data.** `data/raw/D15.xlsx` had a sheet of student names and roll numbers; it was replaced with dummy values before storing. The raw faculty web pages (D30) are **not** in the repository because several contain student names, roll numbers and student emails; only the extracted course lines (`teaching.csv`) and `data/raw/D30_teaching/index.csv` (page URLs) are kept. A scan of every committed file for student identifiers (`\b[BMP]2[0-9][A-Za-z]{2,4}[0-9]{3,4}\b`) found none.
* **Faculty emails** are the ones the institute publishes in its People directory.
* **Campus-only files.** Eight sources are linked from the public website but served only on the campus network or intranet (D15, D23, D24, D26, D27, D29, D32, D33). They are included, for academic use, and flagged `access=campus-network` in `data/sources.csv`. The institute's documents remain the institute's.

---

## 6. Limitations

* **P01 and P08 are wrong in every run of every system.** The models read the superseded attendance rule (or the 75% figure) as a condition for sitting the exam, and they pick the wrong column of the flattened calendar table.
* **Single agent refuses without searching** (28% false refusals, e.g. P03 and P07), because its guard deliberately lets refusals through so that it can reject out-of-scope questions.
* **Routing errors** in the multi-agent version (87% accuracy): "whom to apply to for a make-up exam" (P04) goes to the email agent; P13 and P16 go to the schedule agent. Institute holidays are treated as out of scope (P17, every system).
* **Guard bypass.** The strict "try a tool before refusing" guard counts a call to `log_unanswered` as a tool use, so a model can log and refuse without searching (seen once with Llama, P05).
* **Citations are written by the model**, so a URL can be wrong (0 to 1 of 90 answers per system). A citation shows "p. null" when a tool returns no page.
* **Llama 3.1 8B** was evaluated only as a multi-agent system; its email agent fails (7% accuracy) because it ignores tool results. No other 8B model was tried.
* **Small, self-made question set** (30 questions, 3 runs, one grader). Answers vary between runs (sampling temperature 0.6); the questions whose outcome changed are listed in `REPORT.md`.

---

## 7. Repository layout

```text
agents/             ADK entry points: single_agent/, multi_agent/   (adk web agents)
helpdesk/           config, llm factory, prompts, tools, callbacks (guards), agent builders, runner
scripts/            build_structured.py (raw -> CSV tables), ingest.py (text/OCR -> chunks -> embeddings -> Chroma)
                    build_report_pdf.py (REPORT.md -> REPORT.pdf via headless Edge/Chrome)
data/raw/           collected documents (originals; D15 sanitised); D29_erp/ ERP pages; D28_*.html People directory
data/text/          extracted page text (incl. OCR) cached by ingest.py
data/structured/    courses.csv, slots.csv, faculty.csv, catalogue.csv, teaching.csv
data/sources.csv    provenance of every source
data/chroma/        vector index (NOT committed; created by ingest.py)
eval/               build_questions.py (question set source), questions.csv, run_eval.py, score.py,
                    apply_manual_grades.py, check_sources.py, smoke_test.py, measure_ram.ps1, build_review_sheet.py
eval/results/       raw answers, scores, grades, summaries (final + v1/v2 iterations), RAM samples
eval/review/        question_answer_sheet.xlsx (optional workbook for an independent check of the references)
logs/unanswered.jsonl   the log of questions the agent could not answer (sample from the evaluation runs)
ollama/             Modelfiles (8K context variants of qwen3:8b and llama3.1:8b)
REPORT.pdf          report (built from REPORT.md)       REPORT.md   report source
report/report.tex   LaTeX version of the report
```

## 8. Environment notes

* **Ollama on an RTX 3050 4 GB** (Ollama 0.40.x) crashed with the CUDA 13 backend (`CUDA error: shared object initialization failed`). Fix: set `OLLAMA_LLM_LIBRARY=cuda_v12` before `ollama serve`. Also keep the embedding model on the GPU: on the CPU its threads compete with the CPU-resident layers of the chat model and prompt processing gets ~8x slower.
* The default Ollama context truncates retrieved passages; that is why the models are re-created with `num_ctx 8192` (`ollama/Modelfile*`).
* Qwen3 thinking mode is off by default (`HELPDESK_THINK=0`); with it on, latency multiplies on this GPU. About 64% of the 8B model runs on the CPU, so expect 30-40 s median per question.
* Use the `ollama_chat/` LiteLLM provider, not `ollama/`.
* `python -m ...` and the scripts assume the repository root as the working directory; `.venv`, `data/chroma/`, `outputs/` and generated caches are git-ignored.
