"""ADK callbacks shared by the helpdesk agents."""
import re

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from helpdesk.tools import log_unanswered

REFUSAL_PREFIXES = ("i don't know", "i do not know", "i don’t know")


def _text(llm_response: LlmResponse) -> str:
    content = llm_response.content
    if not content or not content.parts:
        return ""
    return "".join(p.text or "" for p in content.parts if not getattr(p, "thought", False)).strip()


def _has_function_call(llm_response: LlmResponse) -> bool:
    content = llm_response.content
    return bool(content and content.parts and any(p.function_call for p in content.parts))


def _question(callback_context: CallbackContext) -> str:
    user = callback_context.user_content
    return "".join(p.text or "" for p in (user.parts if user and user.parts else []))


def _tools_used_this_turn(callback_context: CallbackContext) -> bool:
    """True if any tool other than agent transfer was called in the current invocation."""
    for ev in callback_context.session.events:
        if ev.invocation_id != callback_context.invocation_id:
            continue
        for fc in ev.get_function_calls():
            if fc.name != "transfer_to_agent":
                return True
    return False


def _is_refusal(text: str) -> bool:
    return text.lower().lstrip("*# ").startswith(REFUSAL_PREFIXES)


def log_refusals(callback_context: CallbackContext, llm_response: LlmResponse):
    """Guarantee that every "I don't know" answer reaches logs/unanswered.jsonl.

    The model is instructed to call log_unanswered itself, but small models sometimes
    skip the call. log_unanswered de-duplicates, so double logging is harmless.
    """
    text = _text(llm_response)
    if text and _is_refusal(text):
        log_unanswered(_question(callback_context),
                       f"auto-logged refusal by {callback_context.agent_name}: {text[:200]}")
    return None


def require_tool(tool_name: str, make_args, force_on_refusal: bool = False):
    """Build an after_model_callback that forces a tool call before a final answer.

    If the model tries to answer without having used any tool in this turn (i.e. from its own memory),
    the answer is discarded and replaced by a call to `tool_name` with make_args(question), so the next
    model step is grounded in tool output.
    Refusals ("I don't know") are let through and logged, unless force_on_refusal is set: specialist
    agents only receive questions the orchestrator judged in scope, so they must try a tool before
    giving up. (The single agent must be able to refuse out-of-scope questions directly.)
    """
    def callback(callback_context: CallbackContext, llm_response: LlmResponse):
        text = _text(llm_response)
        if not text or _has_function_call(llm_response):
            return None
        used = _tools_used_this_turn(callback_context)
        if _is_refusal(text) and (used or not force_on_refusal):
            return log_refusals(callback_context, llm_response)
        if used:
            return None
        call = types.FunctionCall(name=tool_name, args=make_args(_question(callback_context)))
        return LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=call)]))
    return callback


def _course_code(text: str) -> str:
    m = re.search(r"\b([A-Z]{3})\s?(\d{4})\b", text.upper())
    return m.group(1) + m.group(2) if m else ""


def _search_args(q):
    return {"query": q, "top_k": 5}


def _email_args(q):
    return {"course_code": _course_code(q), "instructor_name": q}


# single agent: ground answers in document search; may still refuse out-of-scope questions directly
retrieve_first = require_tool("search_documents", _search_args)
# specialist agents (questions already routed as in scope): try a tool before answering or refusing
retrieve_first_strict = require_tool("search_documents", _search_args, force_on_refusal=True)
lookup_first_strict = require_tool("get_instructor_email", _email_args, force_on_refusal=True)
