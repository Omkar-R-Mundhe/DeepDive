from pydantic import ValidationError

from app.schemas.research import ResearchPlan
from app.services.llm_client import ask_model


class PlannerOutputError(RuntimeError):
    pass


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
    response = ask_model(prompt)

    try:
        return ResearchPlan.model_validate_json(response)
    except ValidationError as exc:
        issues = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors(include_input=False)
        )
        raise PlannerOutputError(
            f"The planner returned invalid structured output: {issues}"
        ) from exc
