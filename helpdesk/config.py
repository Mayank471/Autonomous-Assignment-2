"""Central paths and model settings for the Academic Helpdesk."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
STRUCTURED_DIR = DATA_DIR / "structured"
CHROMA_DIR = DATA_DIR / "chroma"
SOURCES_CSV = DATA_DIR / "sources.csv"

LOG_DIR = ROOT / "logs"
UNANSWERED_LOG = LOG_DIR / "unanswered.jsonl"
EMAIL_DRAFT_DIR = ROOT / "outputs" / "email_drafts"

OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
# LiteLLM model string used by ADK. "ollama_chat/" is required for reliable tool calling.
LLM_MODEL = os.getenv("HELPDESK_LLM", "ollama_chat/qwen3-8b-helpdesk")
EMBED_MODEL = os.getenv("HELPDESK_EMBED", "nomic-embed-text")
CHROMA_COLLECTION = "iitj_docs"
# Extra Ollama options for the embedding model. Keep it on the GPU: on CPU its threads compete
# with the CPU-resident layers of the chat model and prompt processing becomes ~8x slower.
EMBED_OPTIONS: dict = {}

# LiteLLM reads OLLAMA_API_BASE from the environment.
os.environ.setdefault("OLLAMA_API_BASE", OLLAMA_API_BASE)
