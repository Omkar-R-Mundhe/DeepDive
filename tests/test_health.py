import logging

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import ConfigurationError
from app.schemas.research import (
    EvidenceRecord,
    ResearchClaim,
    ResearchPlan,
    ResearchRunResponse,
    VerifiedClaim,
    VerificationRecord,
)
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


def test_request_logging_correlates_stages_without_logging_question(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(main, "ask_model", lambda _: "A private question's answer")
    caplog.set_level(logging.INFO, logger="app")
    private_question = "do not put this question in logs"

    response = client.post(
        "/api/v1/ask",
        json={"question": private_question},
    )

    request_id = response.headers["X-Request-ID"]
    log_output = caplog.text
    assert request_id in log_output
    assert "stage=api.ask event=started" in log_output
    assert "event=request_completed" in log_output
    assert private_question not in log_output


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


def test_draft_endpoint_returns_claims(
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
    claim = ResearchClaim(
        claim_id="C-test123",
        claim_text="Tree cover can reduce local temperatures.",
        evidence_ids=["E-test123"],
        status="unverified",
    )
    monkeypatch.setattr(main, "draft_claims", lambda question, records: [claim])

    response = client.post(
        "/api/v1/claims/draft",
        json={"question": "How does tree cover affect temperature?", "evidence": [
            record.model_dump(mode="json") for record in evidence
        ]},
    )

    assert response.status_code == 200
    assert response.json()["claims"][0]["claim_id"] == "C-test123"
    assert response.json()["claims"][0]["evidence_ids"] == ["E-test123"]


def test_verify_endpoint_returns_verified_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = EvidenceRecord(
        evidence_id="E-test123",
        query="urban trees",
        source_url="https://example.org/tree-study",
        source_title="Urban tree study",
        retrieved_at="2026-10-12T16:00:00+00:00",
        passage="Tree cover can reduce local temperatures.",
    )
    claim = ResearchClaim(
        claim_id="C-test123",
        claim_text="Tree cover can reduce local temperatures.",
        evidence_ids=["E-test123"],
        status="unverified",
    )
    monkeypatch.setattr(
        main,
        "verify_claims",
        lambda claims, records: [
            VerifiedClaim(
                claim=claims[0].model_copy(update={"status": "supported"}),
                verification=VerificationRecord(
                    claim_id="C-test123",
                    verdict="supported",
                    rationale="The passage directly states this.",
                    evidence_ids=["E-test123"],
                    checked_at="2026-10-12T16:00:00+00:00",
                ),
            )
        ],
    )

    response = client.post(
        "/api/v1/claims/verify",
        json={
            "claims": [claim.model_dump()],
            "evidence": [evidence.model_dump(mode="json")],
        },
    )

    assert response.status_code == 200
    result = response.json()["verifications"][0]
    assert result["claim"]["status"] == "supported"
    assert result["verification"]["evidence_ids"] == ["E-test123"]


def test_research_run_endpoint_returns_combined_workflow_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = EvidenceRecord(
        evidence_id="E-test123",
        query="Research question",
        source_url="https://example.org/source",
        source_title="Research source",
        retrieved_at="2026-10-13T16:00:00+00:00",
        passage="A finding in the source.",
    )
    claim = ResearchClaim(
        claim_id="C-test123",
        claim_text="A finding in the source.",
        evidence_ids=["E-test123"],
        status="supported",
    )
    run = ResearchRunResponse(
        question="Research question",
        plan=ResearchPlan(
            sub_questions=["Question one?", "Question two?", "Question three?"],
            scope_boundaries=["Current evidence."],
            recommended_source_types=["Research papers"],
        ),
        evidence=[evidence],
        claims=[claim],
        verifications=[
            VerifiedClaim(
                claim=claim,
                verification=VerificationRecord(
                    claim_id="C-test123",
                    verdict="supported",
                    rationale="The passage states the finding.",
                    evidence_ids=["E-test123"],
                    checked_at="2026-10-13T16:00:00+00:00",
                ),
            )
        ],
    )
    monkeypatch.setattr(main, "run_research", lambda question, results_per_query: run)

    response = client.post(
        "/api/v1/research/run",
        json={"question": "Research question", "results_per_query": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["sub_questions"][0] == "Question one?"
    assert body["evidence"][0]["evidence_id"] == "E-test123"
    assert body["claims"][0]["claim_id"] == "C-test123"
    assert body["verifications"][0]["verification"]["verdict"] == "supported"
