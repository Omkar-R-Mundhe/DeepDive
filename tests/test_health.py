import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import ConfigurationError
from app.schemas.research import EvidenceRecord, ResearchPlan
from app.services.llm_client import LLMProviderError

client = TestClient(main.app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ask_returns_model_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "ask_model", lambda question: f"Answer to: {question}")

    response = client.post("/api/v1/ask", json={"question": "Hello"})

    assert response.status_code == 200
    assert response.json() == {"answer": "Answer to: Hello"}


def test_ask_rejects_blank_question() -> None:
    response = client.post("/api/v1/ask", json={"question": "   "})

    assert response.status_code == 422


def test_ask_reports_missing_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_setting(_: str) -> str:
        raise ConfigurationError("Required setting MESH_API_KEY is missing or empty.")

    monkeypatch.setattr(main, "ask_model", missing_setting)

    response = client.post("/api/v1/ask", json={"question": "Hello"})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Required setting MESH_API_KEY is missing or empty."
    }


def test_ask_reports_mesh_api_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream_error = "Error code: 402 - insufficient balance"

    def failed_request(_: str) -> str:
        raise LLMProviderError(upstream_error)

    monkeypatch.setattr(main, "ask_model", failed_request)

    response = client.post("/api/v1/ask", json={"question": "Hello"})

    assert response.status_code == 502
    assert response.json() == {"detail": upstream_error}


def test_plan_returns_structured_research_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_plan = ResearchPlan(
        sub_questions=["Question one?", "Question two?", "Question three?"],
        scope_boundaries=["Focus on current evidence."],
        recommended_source_types=["Official reports"],
    )
    monkeypatch.setattr(
        main, "create_research_plan", lambda question: expected_plan
    )

    response = client.post(
        "/api/v1/plan",
        json={"question": "Research a topic"},
    )

    assert response.status_code == 200
    assert response.json() == expected_plan.model_dump()


def test_plan_reports_invalid_model_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid_plan(_: str) -> ResearchPlan:
        from app.agents.planner import PlannerOutputError

        raise PlannerOutputError("The planner returned invalid structured output.")

    monkeypatch.setattr(main, "create_research_plan", invalid_plan)

    response = client.post("/api/v1/plan", json={"question": "Research a topic"})

    assert response.status_code == 502
    assert response.json() == {
        "detail": "The planner returned invalid structured output."
    }


def test_research_sources_returns_and_persists_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = [
        EvidenceRecord(
            evidence_id="E-test123",
            query="urban trees",
            source_url="https://example.org/tree-study",
            source_title="Urban tree study",
            retrieved_at="2026-10-12T16:00:00+00:00",
            passage="Tree cover can reduce local temperatures.",
        )
    ]
    saved: list[EvidenceRecord] = []
    monkeypatch.setattr(main, "search_sources", lambda query, count: evidence)
    monkeypatch.setattr(main, "save_evidence", lambda records: saved.extend(records))

    response = client.post(
        "/api/v1/research/sources",
        json={"query": "urban trees", "count": 3},
    )

    assert response.status_code == 200
    assert response.json()["evidence"][0]["evidence_id"] == "E-test123"
    assert response.json()["evidence"][0]["source_type"] == "search_snippet"
    assert saved == evidence


def test_research_sources_reports_missing_brave_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_key(query: str, count: int) -> list[EvidenceRecord]:
        raise ConfigurationError(
            "Required setting BRAVE_SEARCH_API_KEY is missing or empty."
        )

    monkeypatch.setattr(main, "search_sources", missing_key)

    response = client.post(
        "/api/v1/research/sources",
        json={"query": "urban trees"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Required setting BRAVE_SEARCH_API_KEY is missing or empty."
    }
