"""ADK entry point: multi-agent version (orchestrator -> policy / schedule / email). Run: adk web agents"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from helpdesk.agents import build_multi_agent  # noqa: E402

root_agent = build_multi_agent()
