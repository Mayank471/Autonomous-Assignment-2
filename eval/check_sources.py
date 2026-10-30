"""Automatic check of the reference answers: every key fact of an answerable question must occur on a cited
source page (data/text/<doc>.json) or, for D29/D30-style table sources, in data/structured/*.csv.

This is NOT human review. It only shows that the reference answer's key facts are present in the cited
document. `--write` sets verified = "source-check" in eval/questions.csv for the rows that pass and have
no verdict yet.

Usage: python eval/check_sources.py [--write]
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "eval" / "questions.csv"


def norm(s: str) -> str:
    s = s.lower().replace("–", "-").replace("—", "-").replace("’", "'")
    return re.sub(r"\s+", " ", s)


def load_pages(doc: str):
    p = ROOT / "data" / "text" / f"{doc}.json"
    if not p.exists():
        return None
    return {pg["page"]: norm(pg["text"]) for pg in json.load(open(p, encoding="utf-8"))}


def check(q, tables: str):
    """Return the list of key facts not found in any cited source."""
    missing = []
    for fact in q["key_facts"].split(";"):
        alts = [norm(a).strip() for a in fact.split("|") if a.strip()]
        found = False
        for s in q["sources"].split("|"):
            doc, _, page = s.partition(":")
            pages = load_pages(doc)
            if pages is None:
                found = found or any(a in tables for a in alts)
                continue
            for pg, text in pages.items():
                if (not page or str(pg) == page) and any(a in text for a in alts):
                    found = True
        if not found:
            missing.append(fact)
    return missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    tables = " ".join(norm(f.read_text(encoding="utf-8")) for f in (ROOT / "data" / "structured").glob("*.csv"))
    with open(QUESTIONS, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fields = list(rows[0])
    ok = 0
    for q in rows:
        if q["expected_behavior"] != "answer" or not q["key_facts"] or not q["sources"]:
            continue
        missing = check(q, tables)
        print(f"{q['id']:4} {'OK  ' if not missing else 'MISS'} {q['question'][:60]}" + (f"  missing: {missing}" if missing else ""))
        if not missing:
            ok += 1
            if args.write and not q["verified"]:
                q["verified"] = "source-check"
    print(f"{ok} answerable questions with all key facts found in their cited source")
    if args.write:
        with open(QUESTIONS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
