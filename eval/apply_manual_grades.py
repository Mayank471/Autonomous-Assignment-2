"""Record manual review decisions in eval/results/grades_<tag>.csv.

The automatic key-fact check cannot judge everything. For example, an answer may contain the right
number but present a superseded rule as current, or say "does not have a published slot", which the
"no data" pattern does not catch. Each override below was decided by reading the answer against
the expected answer in eval/questions.csv. Rows not listed keep their automatic grade
(manual_correct = auto_correct, note "auto grade confirmed on review").

Usage: python eval/apply_manual_grades.py --tag qwen3-8b; then re-run eval/score.py --tag qwen3-8b.
"""
import argparse
import csv
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
REVIEWER = "reviewer: Claude (to be checked by student)"

SUPERSEDED = ("States 75% but presents the superseded rule (below 75% must score at least a C grade) as "
              "current; the 08-07-2024 circular (D08) delinks examination performance from attendance.")
NO_SLOT_OK = "Says the course has no published slot for the current semester: correct 'no data' handling."
NO_DATA_OK = "Says the documents do not contain this semester's offerings: correct 'no data' handling."

# tag -> {(system, run or None for all runs, question id): (grade, note)}
OVERRIDES = {
    # v1 / v2: earlier system versions, scored against the earlier question set
    "v1-qwen3-8b": {("single", None, "P01"): (0, SUPERSEDED)},
    "v2-qwen3-8b": {
        ("single", None, "P01"): (0, SUPERSEDED),
        ("multi", 3, "P08"): (1, "Dates 19-26 November 2026 correct; weekday range given as Thu-Sun instead of Thu-Thu."),
    },
    # final system (v3)
    "qwen3-8b": {
        ("single", None, "P01"): (0, SUPERSEDED),
        ("multi", 1, "P01"): (0, SUPERSEDED),
        ("multi", 3, "P01"): (0, SUPERSEDED),
        ("single", 1, "S01"): (1, NO_SLOT_OK),
        ("single", 2, "S01"): (1, NO_SLOT_OK),
        ("multi", None, "S01"): (1, NO_SLOT_OK),
    },
    "llama31-8b": {
        ("multi", 1, "P01"): (0, SUPERSEDED),
        ("multi", 1, "S02"): (1, NO_DATA_OK),
        ("multi", 3, "S02"): (1, NO_DATA_OK),
        ("multi", 1, "E03"): (0, "Email ID correct but states it refers to the current semester (AY 2026-27); "
                                 "the data is the AY 2023-24 timetable."),
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="qwen3-8b")
    args = ap.parse_args()
    overrides = OVERRIDES.get(args.tag, {})
    path = RESULTS / f"grades_{args.tag}.csv"
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fields = list(rows[0])
    changed = 0
    for r in rows:
        ov = overrides.get((r["system"], int(r["run"]), r["id"])) or overrides.get((r["system"], None, r["id"]))
        if ov:
            r["manual_correct"], r["reviewer_note"] = str(ov[0]), f"{ov[1]} [{REVIEWER}]"
            changed += int(str(ov[0]) != r["auto_correct"])
        else:
            r["manual_correct"], r["reviewer_note"] = r["auto_correct"], f"auto grade confirmed on review [{REVIEWER}]"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"{args.tag}: {len(rows)} rows reviewed, {changed} automatic grades overridden")


if __name__ == "__main__":
    main()
