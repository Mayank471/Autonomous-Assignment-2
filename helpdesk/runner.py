"""Run a helpdesk agent programmatically (used by the CLI and the evaluation harness).

Usage: python -m helpdesk.runner --system multi "What is the attendance requirement?"
"""
import argparse
import asyncio
import time
import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from helpdesk.agents import build_multi_agent, build_single_agent

APP = "academic_helpdesk"


def build(system: str, model: str | None = None):
    return build_multi_agent(model) if system == "multi" else build_single_agent(model)


async def ask(agent, question: str) -> dict:
    """Ask one question in a fresh session; return the answer and a trace."""
    sessions = InMemorySessionService()
    runner = Runner(app_name=APP, agent=agent, session_service=sessions)
    session = await sessions.create_session(app_name=APP, user_id="student", session_id=str(uuid.uuid4()))
    msg = types.Content(role="user", parts=[types.Part(text=question)])
    tool_calls, agents_seen, texts, error = [], [], [], None
    start = time.perf_counter()
    try:
        async for ev in runner.run_async(user_id="student", session_id=session.id, new_message=msg):
            if ev.author and ev.author != "user" and ev.author not in agents_seen:
                agents_seen.append(ev.author)
            for part in (ev.content.parts if ev.content and ev.content.parts else []):
                if part.function_call:
                    tool_calls.append({"agent": ev.author, "name": part.function_call.name,
                                       "args": dict(part.function_call.args or {})})
                elif part.function_response:
                    resp = part.function_response.response
                    for c in reversed(tool_calls):
                        if c["name"] == part.function_response.name and "response" not in c:
                            c["response"] = resp
                            break
                elif part.text and not getattr(part, "thought", False):
                    texts.append((ev.author, part.text))
    except Exception as e:  # recorded, not hidden: counts as a failed answer in the evaluation
        error = f"{type(e).__name__}: {e}"
    latency = time.perf_counter() - start
    final_author = texts[-1][0] if texts else None
    answer = "\n".join(t for a, t in texts if a == final_author).strip() if texts else ""
    return {"question": question, "answer": answer, "answered_by": final_author,
            "agents": agents_seen, "tool_calls": tool_calls, "latency_s": round(latency, 2),
            "error": error}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--system", choices=["single", "multi"], default="multi")
    ap.add_argument("--model", default=None, help="LiteLLM model string, e.g. ollama_chat/qwen3-8b-helpdesk")
    args = ap.parse_args()
    res = asyncio.run(ask(build(args.system, args.model), args.question))
    for c in res["tool_calls"]:
        print(f"[{c['agent']}] tool {c['name']}({c['args']})")
    print(f"\n[{res['answered_by']}] ({res['latency_s']} s)\n{res['answer']}")
    if res["error"]:
        print("ERROR:", res["error"])


if __name__ == "__main__":
    main()
