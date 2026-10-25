"""ADK entry point: base version (one agent, RAG + all tools). Run: adk web agents"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from helpdesk.agents import build_single_agent  # noqa: E402

root_agent = build_single_agent()
