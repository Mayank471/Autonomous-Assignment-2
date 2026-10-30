# Multi-Agent Academic Helpdesk for IIT Jodhpur: Report

**Course:** Autonomous Systems, Assignment 2

**Group members**

| Name | Roll Number |
|---|---|
| Om Chandra Sharma | B23CS1048 |
| Mayank Dahiya | B23CS1035 |
| Anmol Yadav | B23CS1004 |
| Rudra Gupta | B23CS1098 |

**Models:**
- Qwen3 8B (main) and Llama 3.1 8B (comparison), both Q4 via Ollama;
- nomic-embed-text embeddings, ChromaDB and Google ADK 2.12.

**Hardware:** laptop with 16 GB RAM and an NVIDIA RTX 3050 (4 GB VRAM). Peak memory, measured on this 15.7 GB machine while the 7 assignment example questions ran through the multi-agent system (`eval/measure_ram.ps1`, samples in `eval/results/ram_samples.csv`): Ollama (Qwen3 8B chat model + embedding model) 5.8 GB, Python process 0.4 GB, about 6.2 GB for the whole system; the machine as a whole peaked at 14.2 GB of 15.7 GB including the operating system and other open applications (7.7 GB in use before the run).

## 1. Summary

We built a local helpdesk that answers IIT Jodhpur academic questions:
- **What it does:** cites its sources, drafts emails to instructors, and refuses and logs out-of-scope questions.
- **Data:** everything was obtained by scraping institute web sources: 28 sources, comprising 27 documents plus the faculty directory (D28).
- **Versions:** a single agent with all seven tools, and an orchestrator that routes to policy, schedule and email agents.
- **Evaluation:** 30 questions, including all 7 examples from the assignment, 3 runs each, on both versions. The multi-agent version was also run with a second LLM.

| Final results (3 runs × 30 questions, manually reviewed) | Qwen3 single | **Qwen3 multi-agent** | Llama 3.1 multi-agent |
|---|---|---|---|
| Accuracy on answerable questions | 58% (42/72) | **79% (57/72)** | 50% (36/72) |
| Groundedness: cited document is a correct source | 64% | **83%** | 64% |
| Groundedness: cited document *and page* correct | 58% | **76%** | 54% |
| Correct refusals, out-of-scope (refused and logged) | 100% (12/12) | 100% (12/12) | 100% (12/12) |
| Correct "data not published" handling | 67% (4/6) | **100% (6/6)** | 100% (6/6) |
| False refusals on answerable questions | 28% | **8%** | 12% |
| Answers with a fabricated URL | 0% | 0% | 1% |
| Routing accuracy | – | 87% | 88% |
| Questions whose outcome changed across runs | 10 | **2** | 17 |
| Median latency | 33 s | 40 s | 30 s |

**Key findings.**
1. **Specialisation pays off.** The multi-agent system beats the single agent by 21 points (79% vs 58%), with far fewer false refusals and more stable answers. Each specialist sees few tools and a short prompt. Its weaknesses are misroutes (87% routing accuracy) and misreading tables.
2. **Tool-first guards are the most important design element.** In the first version, the 8B model often answered from memory and invented facts and source URLs: 52% accuracy, 17% fabricated URLs. Callbacks that force a tool call before any answer removed fabricated URLs in the Qwen systems.
3. **Swapping the LLM matters as much as the architecture.** With the same multi-agent system, Llama 3.1 8B scored 29 points lower than Qwen3 8B. Its email agent got the right instructor email from the tool and then said it could not find it, or drafted emails without the draft tool. Its answers changed between runs on 17 of 30 questions, against 2 for Qwen.
4. **All three systems refused all 12 out-of-scope attempts and logged each one.**

## 2. System design

### 2.1 Architecture

```
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

- **Base version:** `agents/single_agent` is one ADK `LlmAgent` with all seven tools.
- **Multi-agent version:** `agents/multi_agent`.
  - The orchestrator has only `log_unanswered` and routes through ADK's `transfer_to_agent`.
  - Specialists cannot transfer back or sideways.
- **Model access:** ADK's LiteLLM connector (`ollama_chat/` provider) with an 8K context set in a Modelfile. Qwen3's thinking mode is off; on a 4 GB GPU it multiplied latency.

### 2.2 Tools

| Tool | Data | Purpose |
|---|---|---|
| `search_documents` | 586 chunks in ChromaDB, plus a BM25 index | Hybrid retrieval. Returns passages with title, page and URL |
| `lookup_course` | `catalogue.csv`, `teaching.csv`, `courses.csv` | Code or name → official catalogue entry, offering history (semester and instructor), and the published slot if any |
| `list_courses` | same | Counts by department, level and type, using the course-code scheme of the Regulations (D01 pp.4–5). Counts either the catalogue or the courses listed as offered in the current semester, and returns the basis of the count |
| `get_slot_timings` | `slots.csv` | Slot → days and times |
| `get_instructor_email` | timetable, `teaching.csv`, `faculty.csv` | Instructor and email by course code or faculty name, with the semester the information refers to |
| `draft_email` | – | Saves a draft for the student to review. Never sends. Missing student details become placeholders |
| `log_unanswered` | `logs/unanswered.jsonl` | Questions to hand over to a human |

**Current semester:** derived from the AY 2026-27 academic calendar (D11 p.1, classes-commencement dates). On the evaluation date it is AY 2026-27 Semester I.

### 2.3 RAG pipeline

1. **Extraction:** PyMuPDF, page by page. Pages without a text layer are OCR'd with Tesseract; these are two circulars and two office orders. Spreadsheets are read sheet by sheet, and HTML pages are cleaned.
2. **Chunking:** about 450 words per chunk with an 80-word overlap. Chunks never cross a page boundary, so every chunk has an exact page for citation.
3. **Embedding:** nomic-embed-text with its task prefixes. The document title is prepended to each chunk.
4. **Retrieval:**
   - Dense top-30 and BM25 top-30 results are combined by reciprocal-rank fusion, and the top 5 are returned.
   - BM25 recovers table rows with exact terms such as "Open Elective" or "75%".
   - The cap of 5 passages is a hardware constraint: generation slows from 6.6 to 2.8 tokens/s as the context grows from 1K to 5K tokens.

### 2.4 Guardrails

- **Grounding prompt:**
  - answer only from tool output;
  - cite as `title, p.N - url`;
  - never write a URL that did not come from a tool;
  - a circular that amends a regulation overrides it;
  - always say which semester slot, instructor or count data refers to;
  - never guess a slot.
- **Tool-first guards** (`helpdesk/callbacks.py`, ADK `after_model_callback`). If a model tries to give a final answer without having called any tool in the turn, the answer is replaced by a forced tool call:
  - `search_documents` for the single, policy and schedule agents;
  - `get_instructor_email` for the email agent.
  - The specialists use a *strict* variant: they must try a tool even before refusing, because the orchestrator has already judged the question in scope.
  - The single agent may refuse directly, since it must reject out-of-scope questions itself.
- **Refusal logging:** every "I don't know" reply is written to the unanswered log even when the model forgets to call `log_unanswered`. Duplicates are removed.

## 3. Data

All data was **scraped**. Every source is listed in `data/sources.csv` with its URL, the page that links to it, the download date, its SHA-256 and its access level. The README (section 5) gives the full list, the access levels and the data gaps.

| ID | Source | Type |
|---|---|---|
| D01 | Academic Regulations, students enrolled from July 2019 onwards (UG + PG) | regulation |
| D04 | Notification 26-10-2020: revised continuation/assistantship norms | regulation |
| D05 | PG Regulations, July 2022 onwards | regulation |
| D08, D09 | Circulars 08-07-2024: attendance policy; one Minor + one Major examination *(scanned, OCR)* | circular |
| D10 | B.Tech Regulations, July 2014 and later (rev. 2018) | regulation |
| D11, D13, D14 | Academic calendars: AY 2026-27, Summer 2026, AY 2025-26 | calendar |
| D15 | Slot System AY 2023-24 Sem I, B.Tech 1st year (slots, courses, coordinators, emails, advisors) | timetable |
| D16–D22 | Curricula: B.Tech CSE (2026+ and earlier), CSE specialisations, B.Tech AIDE, M.Tech CSE/AI; CSE course descriptions | curriculum |
| D23, D24, D26, D27 | HSS courses; institute-wide common courses; electives from other departments; minors | course list |
| D28 | People directory, 13 departments → 319 faculty with public emails | directory |
| D29 | Academic ERP course catalogue, 22 departments → 1,198 approved courses with L-T-P and credits | catalogue |
| D30 | Faculty web pages listing the courses they taught → 192 offerings, 101 courses, 20 faculty | teaching history |
| D31 | School of Liberal Arts, undergraduate bouquet courses by semester | course list |
| D32, D33 | Office orders: Institute Holiday Calendar 2026 (11-12-2025); Course Equivalence and Credit Transfer Committee (13-10-2025) *(scanned, OCR)* | office order |
| D34 | Fee structure AY 2026-27 | registration |

**Data gaps and how they are handled.**
- **Current timetable and floated courses.** No timetable newer than the AY 2023-24 first-year slot system is published, and no list of courses floated this semester exists. We searched the institute site, the old academics and department sites, the old institute website, the Internet Archive, the ERP's public pages and web search. The system therefore:
  - says that no slot is published for courses outside D15;
  - counts "offered this semester" only from faculty pages, and states that this count is a lower bound;
  - gives the most recent listed instructor of a course together with the semester of that record.
- **Assignment examples:** CSL7570 = Introduction to AR and VR. Its most recent listed offering is AY 2024-25 Semester I, by Rajendra Nagar "with Dr Avinash Sharma". Autonomous Systems = CSL7650.
- **Access:** eight sources are reachable only from the IIT Jodhpur campus network (`academics.iitj.ac.in`, `intranet.iitj.ac.in`), although the public site links to them. The institute's internal Communications Repository, which states "internal use only", was deliberately not used.
- **Personal data:** student names and roll numbers in D15 were replaced with dummy values at download time. Only faculty entries (public emails) were kept from the directory.
- **Duplicates:** byte-identical copies of the regulations were detected by hash and indexed once.

## 4. Evaluation method

### 4.1 Questions

`eval/questions.csv` has 30 questions:

| Category | n | Examples | Expected behaviour |
|---|---|---|---|
| Policy | 14 | attendance (assignment example), open-elective credits (assignment example), make-up exam, exam duration, calendar, grades, curricula, course contents, holidays, Liberal Arts bouquets | Answer with citation |
| Schedule | 7 | slot of Autonomous Systems (assignment example), 400-level HSS electives this semester (assignment example), slot of CSL1010, slot G timings, faculty advisor, CSL7570 credits, last instructor of CSL7650 | Answer with citation, or "not published" (S01, S02) |
| Email | 5 | email to the instructor of CSL7570 (assignment example), make-up exam email, two email-ID lookups, sick-leave email | Draft or answer |
| Out of scope | 4 | dining and travel (assignment examples), placements, campus Wi-Fi (distractor) | Refuse and log |

Every expected answer is a verbatim quote from a scraped source, with its acceptable `doc:page` citations.

### 4.2 Protocol and metrics

- Each question is asked in a fresh ADK session, three times per system, at default sampling (temperature 0.6).
- **Systems evaluated:**
  - Qwen3 8B, single agent;
  - Qwen3 8B, multi-agent;
  - Llama 3.1 8B, multi-agent (the LLM replacement).
- **Metrics** (computed by `eval/score.py`):
  - *accuracy:* all key facts present and not a refusal. For "not published" items, the answer must say the data is unavailable or incomplete and invent nothing. For out-of-scope items, the answer must refuse *and* the question must be logged.
  - *groundedness:* the cited document, and the document with page, match an expected source.
  - *retrieval hit:* an expected source was returned by a tool.
  - *fabricated URL:* a URL that is none of the scraped sources or pages.
  - *routing accuracy.*
  - *run-to-run consistency.*
- **Reference answers:** every expected answer is quoted from an official IIT Jodhpur document and taken as true. Two rulings were needed on 2026-10-30. P01: the circular of 08-07-2024 (D08) delinks examination performance from attendance, so there is no attendance requirement to sit the exam. P08: the detailed calendar (D11 p.8, row 79) gives 19-26 November 2026 for the Semester I Major exam. `eval/check_sources.py` confirmed that the key facts of 21 of 22 sourced answerable questions occur on the cited page (the 22nd, S07, matches the ERP catalogue row). This is a consistency check against the sources, not an independent human review.
- **Manual review:** every answer to an in-scope or "not published" question (234 of 270) was read against its expected answer. Out-of-scope answers were checked through the refusal text and the log entry. 17 automatic grades were overridden, with the reasons recorded in `eval/apply_manual_grades.py`. These were answers that:
  - contain "75%" but present the superseded C-grade attendance rule as current, or make 75% a condition for sitting the exam (P01: the 08-07-2024 circular says exam performance is no longer linked to attendance);
  - give correct "no published slot" answers in wording the pattern missed;
  - attach the wrong semester to an email ID.

## 5. Results

### 5.1 Development iterations

| Version | Change | Single-agent accuracy | Fabricated URLs |
|---|---|---|---|
| v1 | base system, no guard | 52% (1 run) | 17% |
| v2 | + retrieve-first guard, course-code parsing fix, minimum of 3 passages | 74% (3 runs) | 0% |
| v3 (final) | + all-scraped data (ERP catalogue, faculty teaching pages, office orders), strict guards for specialists, email-lookup guard, name matching | 58% single / **79% multi** | 0% |

- **v1 and v2** were scored on an earlier version of the question set. Four questions were later replaced to cover the new sources, so the v2 and v3 numbers are not directly comparable.
- **v1 failure mode:** the 8B model answered from memory, e.g. "Major exam December 1–15, 2026", citing a non-existent PDF. The guard removed this failure.
- **v3, single agent:** the strict guards and richer data helped the multi-agent system (v2 → v3: 75% → 79%). The single agent's accuracy fell, because its longer prompt and seven tools led to more refusals *without any tool call*: 28% false refusals, on P03, P07, P12, P14, P16, P17 and S06. Its lenient guard deliberately lets refusals through.

### 5.2 Single agent vs multi-agent (Qwen3 8B)

| Category | Single | Multi |
|---|---|---|
| Policy (14 × 3) | 43% | **64%** |
| Schedule (7 × 3) | 76% | **100%** |
| Email (5 × 3) | 80% | **100%** |
| Out of scope (4 × 3) | 100% | 100% |
| **Answerable overall** | 58% | **79%** |

- **Better tool use.** The multi-agent specialists search before answering and do not give up early.
  - The single agent refused P03 (make-up deadline) and P07 (exam duration) 3/3 without searching. The policy agent answered both 3/3 from D01 and D09.
  - The email agent always used `draft_email`. The single agent wrote E04 as plain text without the instructor's address, 3/3.
- **Superseded rules (P01).** The multi-agent policy agent gave only the revised 2024 rule in run 2 and mixed in the superseded C-grade rule in runs 1 and 3; the single agent presented the superseded rule in all 3. All 6 answers are graded wrong: every one gives 75% as the requirement to sit the exam, while the circular delinks exam performance from attendance.
- **Costs of the multi-agent system:**
  - **Routing:** 87%. P04 ("whom to apply to for a make-up exam") went to the email agent, P13 and P16 went to the schedule agent, and P17 was treated as out of scope by the orchestrator.
  - **Wrong despite search:** P15 ("L" in a course code) was answered wrongly 3/3 by the policy agent, even though it retrieved D01.
  - **Latency:** median 40 s against 33 s, because of the extra routing call.

### 5.3 Replacing the LLM: Qwen3 8B vs Llama 3.1 8B (same multi-agent system)

| Category | Qwen3 8B | Llama 3.1 8B |
|---|---|---|
| Policy | **64%** | 55% |
| Schedule | **100%** | 86% |
| Email | **100%** | 7% |
| Out of scope | 100% | 100% |
| Answerable overall | **79%** | 50% |
| Groundedness (document / page) | **83% / 76%** | 64% / 54% |
| Changed across runs | **2** | 17 |
| Median latency | 40 s | **30 s** |

Llama 3.1 routes about as well (88%) and is faster, but it uses tool outputs poorly. Its failure modes:
- **Ignoring tool results:** `get_instructor_email` returned Rajendra Nagar for CSL7570, and Llama replied "I don't know who the instructor is" (E01). On E05 it returned "couldn't find" after receiving mishra@iitj.ac.in.
- **Not calling `draft_email`:** it wrote drafts in its answer text or omitted the address (E02, E04).
- **Wrong semester:** it stated that 2023-24 timetable data refers to the current semester (E03).
- **Reading the wrong row of a table:** P08 (April 2027 instead of November 2026). It also took the "CS7xx" placeholder from D18 as a course code (P13).
- **One genuinely fabricated URL:** a non-existent "All-Departmental-Webpages" PDF (E01).

### 5.4 Refusals and unavailable data

- **Out of scope:** all three systems refused 12/12 attempts (dining, travel, placements, Wi-Fi), and every one was logged.
- **Data not published:**
  - *S01, slot of Autonomous Systems:* all systems stated that no slot is published for AY 2026-27 Semester I, mostly adding the course code CSL7650 and its last listed offering. No system guessed a slot.
  - *S02, 400-level HSS electives this semester:* the Qwen multi-agent system answered "0, based on faculty web pages; the official list is not public, so this may be incomplete", 3/3. The single agent dropped that caveat in 2 of 3 runs.
- **Assignment example E01 (email to the CSL7570 instructor):** the Qwen systems drafted it to rn@iitj.ac.in 6/6, with placeholders for the student's name, reason and dates, and stated that the instructor information is from AY 2024-25.
- **Over-refusal:** P17 (Dussehra holiday, from the scanned holiday office order) was treated as out of scope by every system. The scope definition lists the academic calendar but not institute holidays, so this is a scope-definition issue as much as a model error.

### 5.5 Questions whose answers changed across runs

| System | Questions whose outcome changed | What varied |
|---|---|---|
| Qwen3 multi | P02, P10 | P02 and P10: only the cited documents changed (D01/D05/D10/D16/D20 contain the same clause or table) |
| Qwen3 single | P01, P02, P04, P05, P08, P10, P12, P14, S01, S02 | P12, P14: correct answer vs refusal. P02: run 1 gave no OE number. S02: the caveat appeared only in run 3. P08: wrong date vs refusal. Others: cited documents |
| Llama 3.1 multi | E01–E05, P01, P02, P04, P05, P08, P13, P15, P16, S02, S03, S06, S07 | Routing varied (S07 and P16 went to different agents in different runs), refusals varied (E04, E05, P05), and tool use varied |

Some answers changed while the outcome stayed the same. For example, Qwen multi-agent P08 gave "10–13 July 2027" in two runs and "4–6 August 2027" in another, wrong every time.

Questions wrong in every run of the Qwen multi-agent system:
- P08 (calendar table);
- P15 ("L" read as a department);
- P17 (holiday treated as out of scope);
- P04 (misrouted).

### 5.6 Error analysis

1. **Table misreading (P08, all systems).** The calendar PDF flattens into rows where "4–6 January 2027", "10–13 July 2027" and "19–26 November 2026" sit side by side, and the models pick the wrong column.
2. **Superseded rules (P01).** D01 and the "existing policy" paragraph in D08 both state the old C-grade rule. The models merge it with the revised rule, and even when they quote the revised rule they say 75% is the requirement to sit the exam. The reference answer (ruled from the official circular, D08) is that there is no attendance requirement to sit the exam: examination performance "is no longer linked to their course attendance"; 75% is only the level attendance should not fall below. No run of any system said this, so P01 is wrong in all 9 runs.
3. **Surface-word routing (P04).** "Apply … permission" sends the question to the email agent.
4. **Refusal without trying.** This is the single agent's main failure: the lenient guard lets refusals through. In one Llama run the strict guard was bypassed because calling `log_unanswered` counted as "a tool was used" (P05). The guard should ignore that tool.
5. **Tool-output comprehension (Llama 3.1).** It is given the right instructor and email, then states the opposite.
6. **Batch-dependent requirements (P02).** Open electives are 10 credits under the 2019 regulations and 12 under the 2026 CSE curriculum; answers usually give one value. They often add the 180-credit total from the 2014 regulations.

## 6. Limitations and future work

- **No current timetable or offering list is publicly available.** "This semester" answers rely on faculty pages; only 20 of 261 faculty list courses with years. With the official AY 2026-27 timetable, S01 and S02 would become ordinary questions.
- **Campus-only sources.** Eight sources are campus-network only, so the raw files should not be published outside the institute.
- **Hardware latency.** About 64% of the model runs on the CPU, giving a median latency of 30–40 s.
- **Grading.** Manual review was done by the system author against verbatim references; a second grader would strengthen it.
- **Possible improvements:**
  - ignore `log_unanswered` in the guard;
  - row-wise, table-aware chunking for calendars;
  - few-shot routing examples;
  - scope wording that covers holidays and office orders;
  - citations rendered from tool results rather than written by the model;
  - a larger model, or Qwen3 with thinking enabled on a bigger GPU.

## 7. Reproducing the results

```bash
# the collected data is already in data/ (README section 5.3 describes how it was collected)
python scripts/build_structured.py && python scripts/ingest.py
python eval/build_questions.py
python eval/run_eval.py --system both --runs 3                       # about 3 h with Llama below
python eval/run_eval.py --system multi --runs 3 --model ollama_chat/llama31-8b-helpdesk --tag llama31-8b
for t in qwen3-8b llama31-8b; do python eval/score.py --tag $t; python eval/apply_manual_grades.py --tag $t; python eval/score.py --tag $t; done
```

**Raw outputs** in `eval/results/`:
- `{single,multi}_qwen3-8b.jsonl` and `multi_llama31-8b.jsonl`: answers, tool calls with arguments and results, answering agent, latency;
- `scores_*.csv`, `grades_*.csv` (manual review) and `summary_*.md`;
- `*_v1-*` and `*_v2-*`: the earlier iterations;
- `logs/unanswered.jsonl`: the log of questions for a human to answer.
