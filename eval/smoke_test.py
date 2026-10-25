"""Quick end-to-end check: ask the 7 example questions from the assignment text and print, for each,
the agents involved, the tools called (with arguments), the latency and the answer.

Needs Ollama running with the models from the README. Takes ~5-10 minutes on a 4 GB GPU.

Usage: python eval/smoke_test.py [--system multi|single] [--model ollama_chat/<model>]
"""
import argparse
import asyncio
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

from helpdesk.runner import ask, build  # noqa: E402

EXAMPLES = [
    "What is the attendance requirement to sit in the Major exam?",
    "What is the slot for the course Autonomous Systems?",
    "How many 400 level electives have been floated by the Humanities department in this semester?",
    "How many Open Elective credits do I need to earn in order to get a B.Tech. Degree?",
    "Write an email to the course instructor of CSL7570 that I need leave for 2 days",
    "What are the available dining options on the campus?",
    "What is the best way to reach the campus from Jodhpur city center?",
]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", choices=["single", "multi"], default="multi")
    ap.add_argument("--model", default=None)
    args = ap.parse_args()
    agent = build(args.system, args.model)
    for q in EXAMPLES:
        r = await ask(agent, q)
        tools = [f"{c['name']}({', '.join(f'{k}={str(v)[:30]!r}' for k, v in c['args'].items())})"
                 for c in r["tool_calls"] if c["name"] != "transfer_to_agent"]
        print(f"\nQ: {q}\n   answered by: {r['answered_by']} | {r['latency_s']} s | "
              f"tools: {tools or 'none'}{' | ERROR ' + r['error'] if r['error'] else ''}")
        print("   A: " + r["answer"][:600].replace("\n", "\n      "), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
