"""Builders for the single-agent (base) and multi-agent helpdesk."""
from google.adk.agents import LlmAgent

from helpdesk import prompts
from helpdesk.callbacks import (log_refusals, lookup_first_strict, retrieve_first,
                                retrieve_first_strict)
from helpdesk.llm import make_llm
from helpdesk.tools import (draft_email, get_instructor_email, get_slot_timings, list_courses,
                            log_unanswered, lookup_course, search_documents)


def build_single_agent(model: str | None = None) -> LlmAgent:
    return LlmAgent(
        name="academic_helpdesk",
        model=make_llm(model),
        description="IIT Jodhpur academic helpdesk (single agent with RAG and all tools).",
        instruction=prompts.SINGLE_AGENT,
        tools=[search_documents, lookup_course, list_courses, get_slot_timings,
               get_instructor_email, draft_email, log_unanswered],
        after_model_callback=retrieve_first,
    )


def build_multi_agent(model: str | None = None) -> LlmAgent:
    # Sub-agents answer and finish; they do not bounce the question back or sideways.
    common = dict(disallow_transfer_to_parent=True, disallow_transfer_to_peers=True)
    policy = LlmAgent(
        name="policy_agent", model=make_llm(model),
        description="Answers questions on academic rules and regulations, attendance, exams, grading, "
                    "credits/degree requirements, programmes, curricula, course contents, academic calendar.",
        instruction=prompts.POLICY_AGENT,
        tools=[search_documents, log_unanswered], after_model_callback=retrieve_first_strict, **common)
    schedule = LlmAgent(
        name="schedule_agent", model=make_llm(model),
        description="Answers questions on course slots, timetable, class timings, courses offered/floated "
                    "in a semester, counts of courses by department/level, and course instructors.",
        instruction=prompts.SCHEDULE_AGENT,
        tools=[lookup_course, list_courses, get_slot_timings, get_instructor_email,
               search_documents, log_unanswered], after_model_callback=retrieve_first_strict, **common)
    email = LlmAgent(
        name="email_agent", model=make_llm(model),
        description="Finds a course instructor's email ID and drafts emails to instructors "
                    "(sick leave, makeup exam permission) for the student to review.",
        instruction=prompts.EMAIL_AGENT,
        tools=[get_instructor_email, lookup_course, draft_email, log_unanswered],
        after_model_callback=lookup_first_strict, **common)
    return LlmAgent(
        name="helpdesk_orchestrator",
        model=make_llm(model),
        description="Routes academic helpdesk questions to the policy, schedule or email agent.",
        instruction=prompts.ORCHESTRATOR,
        tools=[log_unanswered],
        sub_agents=[policy, schedule, email],
        after_model_callback=log_refusals,
    )
