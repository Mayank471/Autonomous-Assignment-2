"""Score evaluation results and write per-item and summary tables.

Metrics per answer (automatic). eval/results/grades_<tag>.csv holds a manual_correct column; where a
reviewer has filled it (1/0), it overrides the automatic `correct` value in the summary.
  correct        answer/draft: all key facts present and not a refusal
                 no_data: says it does not know / data unavailable, and invents no instructor email
                 refuse: refuses ("I don't know") and the question was logged
  refused        answer starts with / states "I don't know"
  grounded_doc   a cited document is one of the expected sources
  grounded_page  a cited (document, page) pair matches an expected source (page-less sources match by doc)
  retrieval_hit  an expected source was among the passages/rows returned by the tools
  routed_ok      (multi-agent) the answering agent matches the expected route
  fabricated_citation  the answer contains a URL that is not one of the collected sources
Consistency: for each (system, question), whether correctness, refusal or the cited documents changed
across runs, plus the mean pairwise text similarity of the answers.

Usage: python eval/score.py [--tag qwen3-8b]
"""
import argparse
import csv
import difflib
import itertools
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "eval" / "results"
REFUSAL_RE = re.compile(r"\b(i\s+(do\s*n[o']t|don’t)\s+know)\b", re.I)
UNAVAILABLE_RE = re.compile(r"(i\s+(do\s*n[o']t|don’t)\s+know|not (available|found|present|included|listed|"
                            r"published|public)|no (information|data|record|slot)|does not (appear|contain|include)|"
                            r"could not find|couldn't find|unable to (find|locate)|(may be|is) incomplete|"
                            r"lower bound)", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
URL_RE = re.compile(r"https?://[^\s)\]>\"'`]+")


def norm(s: str) -> str:
    s = s.lower().replace("–", "-").replace("—", "-").replace("’", "'")
    return re.sub(r"\s+", " ", s)


def facts_present(answer: str, key_facts: str) -> bool:
    if not key_facts:
        return True
    a = norm(answer)
    for fact in key_facts.split(";"):
        alts = [norm(x).strip() for x in fact.split("|") if x.strip()]
        ok = False
        for alt in alts:
            # short tokens (e.g. slot "G", "N", "7") must match as whole words
            pat = r"(?<![\w@.])" + re.escape(alt) + r"(?![\w@])" if len(alt) <= 3 else re.escape(alt)
            if re.search(pat, a):
                ok = True
                break
        if not ok:
            return False
    return True


def load_sources():
    with open(ROOT / "data" / "sources.csv", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["status"] == "ok"]


def _u(url: str) -> str:
    """URL key ignoring scheme and trailing slash (http->https rewrites point to the same document)."""
    return url.split("://", 1)[-1].rstrip("/").lower()


def known_urls(sources) -> set:
    urls = {_u(s["url"]) for s in sources} | {_u(s["listed_on"]) for s in sources}
    fac = ROOT / "data" / "structured" / "faculty.csv"
    if fac.exists():
        with open(fac, encoding="utf-8") as f:
            urls |= {_u(r["profile_url"]) for r in csv.DictReader(f) if r["profile_url"]}
    # individual scraped pages of the multi-page sources: faculty teaching pages (D30), ERP pages (D29)
    teach = ROOT / "data" / "raw" / "D30_teaching" / "index.csv"
    if teach.exists():
        with open(teach, encoding="utf-8") as f:
            urls |= {_u(r["url"]) for r in csv.DictReader(f)}
    erp = ROOT / "data" / "raw" / "D29_erp"
    if erp.exists():
        urls |= {_u(f"http://academics.iitj.ac.in:8080/ERP_IITJ/courses.do?dept={p.stem}") for p in erp.glob("*.html")}
    return urls


def fabricated_urls(answer: str, urls: set) -> list:
    return [x for x in URL_RE.findall(answer) if _u(x.rstrip(".,;:*")) not in urls]


def cited(answer: str, sources) -> set:
    """(doc_id, page or None) pairs cited in the answer, matched by title or URL per line."""
    out = set()
    for line in answer.splitlines():
        low = line.lower()
        for s in sources:
            if s["title"].lower() in low or (s["url"] and s["url"].lower() in low):
                m = re.search(r"\bp(?:age)?\.?\s*(\d+)", line, re.I)
                out.add((s["doc_id"], int(m.group(1)) if m else None))
    return out


def expected_pairs(spec: str):
    pairs = []
    for x in filter(None, spec.split("|")):
        doc, _, page = x.partition(":")
        pairs.append((doc, int(page) if page else None))
    return pairs


def retrieved(tool_calls) -> set:
    got = set()
    for c in tool_calls:
        resp = c.get("response") or {}
        for r in resp.get("results", []) if isinstance(resp, dict) else []:
            if "doc_id" in r:
                got.add((r["doc_id"], r.get("page")))
            cit = r.get("citation") if isinstance(r, dict) else None
            if cit:
                got.add((cit["doc_id"], cit.get("page")))
        for r in resp.get("courses", []) if isinstance(resp, dict) else []:
            got.add((r.get("source_doc_id"), None))
        if isinstance(resp, dict) and resp.get("citation"):
            got.add((resp["citation"]["doc_id"], resp["citation"].get("page")))
    return got


def match(pairs_found, expected, page_level: bool) -> bool:
    for doc, page in pairs_found:
        for edoc, epage in expected:
            if doc == edoc and (not page_level or epage is None or page == epage):
                return True
    return False


def score_item(q, r, sources, urls):
    ans = r.get("answer") or ""
    calls = r.get("tool_calls") or []
    beh = q["expected_behavior"]
    refused = bool(REFUSAL_RE.search(ans[:300]))
    drafts = [c for c in calls if c["name"] == "draft_email"]
    draft_text = " ".join(json.dumps(c.get("args", {})) for c in drafts)
    exp = expected_pairs(q["sources"])
    cits = cited(ans, sources)
    # an email draft cites through the draft tool result as well as the answer text
    if beh == "draft":
        facts_ok = facts_present(ans + " " + draft_text, q["key_facts"]) and bool(drafts)
    else:
        facts_ok = facts_present(ans, q["key_facts"])
    if beh in ("answer", "draft"):
        correct = facts_ok and not refused and not r.get("error")
    elif beh == "no_data":
        invented = bool(EMAIL_RE.search(ans + draft_text))
        correct = bool(UNAVAILABLE_RE.search(ans)) and not invented and not r.get("error")
    else:  # refuse
        correct = refused and bool(r.get("logged_unanswered"))
    routes = q["expected_route"].split("|")
    if r["system"] == "multi":
        routed_ok = (r.get("answered_by") == "helpdesk_orchestrator") if routes == ["refuse"] \
            else (r.get("answered_by") in routes)
    else:
        routed_ok = None
    return {
        "system": r["system"], "run": r["run"], "id": q["id"], "category": q["category"],
        "behavior": beh, "correct": int(correct), "refused": int(refused),
        "logged": int(bool(r.get("logged_unanswered"))),
        "grounded_doc": int(match(cits, exp, False)) if exp else "",
        "grounded_page": int(match(cits, exp, True)) if exp else "",
        "retrieval_hit": int(match(retrieved(calls), exp, False)) if exp else "",
        "routed_ok": "" if routed_ok is None else int(routed_ok),
        "answered_by": r.get("answered_by"), "latency_s": r.get("latency_s"),
        "cited_docs": " ".join(sorted({d for d, _ in cits})),
        "fabricated_citation": int(bool(fabricated_urls(ans, urls))),
        "error": r.get("error") or "",
    }


def pct(xs):
    xs = [x for x in xs if x != ""]
    return f"{100 * sum(xs) / len(xs):.0f}% ({sum(xs)}/{len(xs)})" if xs else "-"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="qwen3-8b")
    args = ap.parse_args()
    with open(ROOT / "eval" / "questions.csv", encoding="utf-8") as f:
        questions = {q["id"]: q for q in csv.DictReader(f)}
    sources = load_sources()
    urls = known_urls(sources)

    rows, answers, answers_by_key = [], {}, {}
    for system in ("single", "multi"):
        path = RESULTS / f"{system}_{args.tag}.jsonl"
        if not path.exists():
            continue
        latest = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            latest[(r["run"], r["id"])] = r  # keep the last attempt of each (run, id)
        for (run, qid), r in sorted(latest.items()):
            if qid in questions:
                rows.append(score_item(questions[qid], r, sources, urls))
                answers.setdefault((system, qid), []).append(r.get("answer") or "")
                answers_by_key[(system, run, qid)] = r.get("answer") or ""

    if not rows:
        raise SystemExit("no results found")

    # manual review sheet: auto score + a manual_correct column a human can fill (1/0) with a note.
    grades_path = RESULTS / f"grades_{args.tag}.csv"
    manual = {}
    if grades_path.exists():
        with open(grades_path, encoding="utf-8") as f:
            for g in csv.DictReader(f):
                manual[(g["system"], int(g["run"]), g["id"])] = g
    gfields = ["system", "run", "id", "question", "expected_answer", "answer", "auto_correct",
               "manual_correct", "reviewer_note"]
    with open(grades_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=gfields)
        w.writeheader()
        for r in rows:
            key = (r["system"], r["run"], r["id"])
            old = manual.get(key, {})
            w.writerow({"system": r["system"], "run": r["run"], "id": r["id"],
                        "question": questions[r["id"]]["question"],
                        "expected_answer": questions[r["id"]]["expected_answer"],
                        "answer": answers_by_key[key], "auto_correct": r["correct"],
                        "manual_correct": old.get("manual_correct", ""),
                        "reviewer_note": old.get("reviewer_note", "")})
            r["auto_correct"] = r["correct"]
            if old.get("manual_correct", "") in ("0", "1"):
                r["correct"] = int(old["manual_correct"])
                r["manually_graded"] = 1
            else:
                r["manually_graded"] = 0
    with open(RESULTS / f"scores_{args.tag}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    md = [f"# Evaluation summary ({args.tag})", ""]
    for system in ("single", "multi"):
        rs = [r for r in rows if r["system"] == system]
        if not rs:
            continue
        ans = [r for r in rs if r["behavior"] in ("answer", "draft")]
        oos = [r for r in rs if r["behavior"] == "refuse"]
        nod = [r for r in rs if r["behavior"] == "no_data"]
        md += [f"## {system}-agent ({len({r['run'] for r in rs})} runs x {len({r['id'] for r in rs})} questions)", "",
               "| Metric | Value |", "|---|---|",
               f"| Accuracy, answerable questions | {pct([r['correct'] for r in ans])} |",
               f"| Accuracy, answerable questions (automatic key-fact check only) | {pct([r['auto_correct'] for r in ans])} |",
               f"| Items manually graded | {sum(r['manually_graded'] for r in rs)}/{len(rs)} |",
               f"| Groundedness, cited doc matches source | {pct([r['grounded_doc'] for r in ans])} |",
               f"| Groundedness, cited doc+page matches | {pct([r['grounded_page'] for r in ans])} |",
               f"| Retrieval hit (expected source returned by a tool) | {pct([r['retrieval_hit'] for r in ans])} |",
               f"| Correct refusal, out-of-scope (refused and logged) | {pct([r['correct'] for r in oos])} |",
               f"| Out-of-scope refused (ignoring logging) | {pct([r['refused'] for r in oos])} |",
               f"| Correct 'no data' handling (assignment items without public data) | {pct([r['correct'] for r in nod])} |",
               f"| False refusals on answerable questions | {pct([r['refused'] for r in ans])} |",
               f"| Answers containing a fabricated URL (all questions) | {pct([r['fabricated_citation'] for r in rs])} |",
               ]
        if system == "multi":
            md.append(f"| Routing accuracy | {pct([r['routed_ok'] for r in rs])} |")
        lat = sorted(r["latency_s"] for r in rs if r["latency_s"] is not None)
        md += [f"| Median latency | {statistics.median(lat):.0f} s |" if lat else "", f"| Errors | {sum(bool(r['error']) for r in rs)} |", ""]
        md += ["| Category | Accuracy |", "|---|---|"]
        for cat in ("policy", "schedule", "email", "out_of_scope"):
            md.append(f"| {cat} | {pct([r['correct'] for r in rs if r['category'] == cat])} |")
        md.append("")

        # consistency across runs
        md += ["### Run-to-run consistency", "",
               "| Question | Correct per run | Refused per run | Cited docs per run | Answer similarity | Changed |",
               "|---|---|---|---|---|---|"]
        by_q = {}
        for r in rs:
            by_q.setdefault(r["id"], []).append(r)
        changed = []
        for qid, items in by_q.items():
            items.sort(key=lambda x: x["run"])
            if len(items) < 2:
                continue
            texts = answers[(system, qid)]
            sims = [difflib.SequenceMatcher(None, a, b).ratio() for a, b in itertools.combinations(texts, 2)]
            ch = len({i["correct"] for i in items}) > 1 or len({i["refused"] for i in items}) > 1 \
                or len({i["cited_docs"] for i in items}) > 1
            if ch:
                changed.append(qid)
            md.append(f"| {qid} | {' '.join(str(i['correct']) for i in items)} | "
                      f"{' '.join(str(i['refused']) for i in items)} | "
                      f"{' / '.join(i['cited_docs'] or '-' for i in items)} | "
                      f"{sum(sims) / len(sims):.2f} | {'YES' if ch else ''} |")
        md += ["", f"Questions whose outcome changed across runs: {', '.join(changed) or 'none'}", ""]

    (RESULTS / f"summary_{args.tag}.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
