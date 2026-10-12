import pytest
from pydantic import ValidationError

from app.agents import planner
from app.schemas.research import ResearchPlan


def test_create_research_plan_parses_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = (
        '{"sub_questions":["Question one?","Question two?","Question three?"],'
        '"scope_boundaries":["Use current evidence."],'
        '"recommended_source_types":["Official reports"]}'
    )
    monkeypatch.setattr(planner, "ask_model", lambda _: response)

    plan = planner.create_research_plan("Research this topic")

    assert plan == ResearchPlan(
        sub_questions=["Question one?", "Question two?", "Question three?"],
        scope_boundaries=["Use current evidence."],
        recommended_source_types=["Official reports"],
    )


@pytest.mark.parametrize(
    "sub_questions",
    [
        ["Only one?"],
        ["One?", "Two?"],
        ["One?", "Two?", "Three?", "Four?", "Five?", "Six?"],
        ["Same?", "same?", "Different?"],
    ],
)
def test_research_plan_rejects_invalid_sub_question_counts_or_duplicates(
    sub_questions: list[str],
) -> None:
    with pytest.raises(ValidationError):
        ResearchPlan(
            sub_questions=sub_questions,
            scope_boundaries=["Boundary"],
            recommended_source_types=["Official reports"],
        )


def test_create_research_plan_rejects_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(planner, "ask_model", lambda _: "not JSON")

    with pytest.raises(planner.PlannerOutputError, match="invalid structured output"):
        planner.create_research_plan("Research this topic")
