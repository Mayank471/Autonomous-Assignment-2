"""LLM factory: an Ollama-hosted model through ADK's LiteLLM connector."""
import os

from google.adk.models.lite_llm import LiteLlm

from helpdesk.config import LLM_MODEL, OLLAMA_API_BASE


def make_llm(model: str | None = None) -> LiteLlm:
    # Qwen3 "thinking" multiplies latency on a 4 GB GPU; it is off unless HELPDESK_THINK=1.
    think = os.getenv("HELPDESK_THINK", "0") == "1"
    return LiteLlm(model=model or LLM_MODEL, api_base=OLLAMA_API_BASE, think=think)
