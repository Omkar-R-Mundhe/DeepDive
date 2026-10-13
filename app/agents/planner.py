import logging

from pydantic import ValidationError

from app.logging_utils import log_event, log_stage
from app.schemas.research import ResearchPlan
from app.services.llm_client import ask_model


class PlannerOutputError(RuntimeError):
    pass


logger = logging.getLogger(__name__)


def create_research_plan(question: str) -> ResearchPlan:
    prompt = f"""You are the planning component of a research system.
Turn the user's research question into 3 to 5 distinct, focused sub-questions.
Do not answer the research question or assert research findings.
Identify scope boundaries and useful source types for the research.
Return only a JSON object with exactly these keys:
{{
  "sub_questions": ["..."],
  "scope_boundaries": ["..."],
  "recommended_source_types": ["..."]
}}

Research question:
{question}"""
    with log_stage(logger, "planner.generate"):
        response = ask_model(prompt)

    try:
        with log_stage(logger, "planner.validate_output"):
            plan = ResearchPlan.model_validate_json(response)
    except ValidationError as exc:
        issues = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors(include_input=False)
        )
        raise PlannerOutputError(
            f"The planner returned invalid structured output: {issues}"
        ) from exc
    log_event(
        logger,
        "planner.output",
        "validated",
        sub_question_count=len(plan.sub_questions),
        scope_boundary_count=len(plan.scope_boundaries),
        source_type_count=len(plan.recommended_source_types),
    )
    return plan
