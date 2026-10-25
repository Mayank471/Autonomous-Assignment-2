"""Run the evaluation questions through the helpdesk and save raw results.

Each question is asked in a fresh session, `--runs` times, for each system.
Results are appended to a JSONL file incrementally, and finished (system, run, id)
triples are skipped on restart, so a long run can be resumed.

Usage:
  python eval/run_eval.py --system both --runs 3
  python eval/run_eval.py --system multi --runs 1 --ids P01,O01
  python eval/run_eval.py --system multi --model ollama_chat/llama3.1:8b --tag llama31
"""
import argparse
import asyncio
import csv
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from helpdesk.config import LLM_MODEL, UNANSWERED_LOG  # noqa: E402
from helpdesk.runner import ask, build  # noqa: E402

RESULTS = ROOT / "eval" / "results"


def log_lines() -> int:
    return len(UNANSWERED_LOG.read_text(encoding="utf-8").splitlines()) if UNANSWERED_LOG.exists() else 0


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", choices=["single", "multi", "both"], default="both")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--ids", default="", help="comma-separated question ids (default: all)")
    ap.add_argument("--model", default=None, help=f"LiteLLM model string (default {LLM_MODEL})")
    ap.add_argument("--tag", default="qwen3-8b", help="label used in the output file name")
    args = ap.parse_args()

    with open(ROOT / "eval" / "questions.csv", encoding="utf-8") as f:
        questions = list(csv.DictReader(f))
    if args.ids:
        wanted = set(args.ids.split(","))
        questions = [q for q in questions if q["id"] in wanted]

    RESULTS.mkdir(parents=True, exist_ok=True)
    systems = ["single", "multi"] if args.system == "both" else [args.system]
    for system in systems:
        out = RESULTS / f"{system}_{args.tag}.jsonl"
        done = set()
        if out.exists():
            for line in out.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                if not r.get("error"):
                    done.add((r["run"], r["id"]))
        agent = build(system, args.model)
        for run in range(1, args.runs + 1):
            for q in questions:
                if (run, q["id"]) in done:
                    continue
                before = log_lines()
                res = await ask(agent, q["question"])
                res.update(id=q["id"], run=run, system=system, model=args.model or LLM_MODEL,
                           logged_unanswered=log_lines() > before)
                with open(out, "a", encoding="utf-8") as f:
                    f.write(json.dumps(res, ensure_ascii=False, default=str) + "\n")
                print(f"[{system} run{run}] {q['id']} {res['latency_s']:>6}s "
                      f"by={res['answered_by']} {'ERROR ' + res['error'] if res['error'] else ''}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
