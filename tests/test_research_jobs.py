import pytest

from app.schemas.research import (
    ResearchPlan,
    ResearchReport,
    ResearchReportSection,
    ResearchRunResponse,
)
from app.services import research_jobs


def make_result() -> ResearchRunResponse:
    return ResearchRunResponse(
        question="Research question",
        report=ResearchReport(
            answer="A synthesized answer.",
            sections=[
                ResearchReportSection(
                    heading="Finding",
                    body="A verified finding.",
                    evidence_ids=[],
                )
            ],
        ),
        plan=ResearchPlan(
            sub_questions=["Question one?", "Question two?", "Question three?"],
            scope_boundaries=["Current evidence."],
            recommended_source_types=["Research papers"],
        ),
        evidence=[],
        claims=[],
        verifications=[],
    )


def test_execute_research_job_persists_progress_and_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = []
    result = make_result()

    def record_update(run_id: str, **kwargs: object) -> None:
        updates.append((run_id, kwargs))

    def fake_run(
        question: str,
        results_per_query: int,
        progress_callback,
    ) -> ResearchRunResponse:
        assert question == "Research question"
        assert results_per_query == 2
        progress_callback("Planning research")
        progress_callback("Drafting claims")
        return result

    monkeypatch.setattr(research_jobs, "update_research_run", record_update)
    monkeypatch.setattr(research_jobs, "run_research", fake_run)

    research_jobs.execute_research_job("run-1", "Research question", 2)

    assert [update[1]["current_stage"] for update in updates] == [
        "Starting research",
        "Planning research",
        "Drafting claims",
        "Research complete",
    ]
    assert updates[-1][1]["status"] == "completed"
    assert updates[-1][1]["result"] == result


def test_execute_research_job_persists_failure_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = []

    def record_update(run_id: str, **kwargs: object) -> None:
        updates.append(kwargs)

    def failed_run(*args: object, **kwargs: object) -> ResearchRunResponse:
        raise research_jobs.ConfigurationError("Missing Tavily API key.")

    monkeypatch.setattr(research_jobs, "update_research_run", record_update)
    monkeypatch.setattr(research_jobs, "run_research", failed_run)

    research_jobs.execute_research_job("run-2", "Research question", 2)

    assert updates[-1]["status"] == "failed"
    assert updates[-1]["current_stage"] == "Research failed"
    assert updates[-1]["error"] == (
        "The research service is not fully configured. Check the provider "
        "and API-key settings on the server."
    )


def test_execute_research_job_hides_raw_provider_quota_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = []
    provider_error = (
        "Error code: 429 RESOURCE_EXHAUSTED: exceeded free tier quota "
        "for generativelanguage.googleapis.com"
    )

    def record_update(run_id: str, **kwargs: object) -> None:
        updates.append(kwargs)

    def failed_run(*args: object, **kwargs: object) -> ResearchRunResponse:
        raise research_jobs.LLMProviderError(provider_error)

    monkeypatch.setattr(research_jobs, "update_research_run", record_update)
    monkeypatch.setattr(research_jobs, "run_research", failed_run)

    research_jobs.execute_research_job("run-3", "Research question", 2)

    error = updates[-1]["error"]
    assert "quota" in error.lower()
    assert "generativelanguage.googleapis.com" not in error
    assert "RESOURCE_EXHAUSTED" not in error


def test_execute_research_job_explains_provider_insufficient_credits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = []

    def record_update(run_id: str, **kwargs: object) -> None:
        updates.append(kwargs)

    def failed_run(*args: object, **kwargs: object) -> ResearchRunResponse:
        raise research_jobs.LLMProviderError(
            "Error code: 402 - insufficient credits"
        )

    monkeypatch.setattr(research_jobs, "update_research_run", record_update)
    monkeypatch.setattr(research_jobs, "run_research", failed_run)

    research_jobs.execute_research_job("run-4", "Research question", 2)

    error = updates[-1]["error"]
    assert "insufficient credits" in error.lower()
    assert "add credits" in error.lower()
