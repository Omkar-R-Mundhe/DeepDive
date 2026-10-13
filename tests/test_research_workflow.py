from datetime import datetime, timezone

import pytest

from app.agents import research_workflow
from app.schemas.research import (
    EvidenceRecord,
    ResearchClaim,
    ResearchPlan,
    ResearchRunResponse,
    VerifiedClaim,
    VerificationRecord,
)


def make_evidence(query: str, evidence_id: str) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        query=query,
        source_url=f"https://example.org/{evidence_id}",
        source_title=f"Source for {query}",
        retrieved_at=datetime.now(timezone.utc),
        passage=f"Evidence about {query}.",
    )


def test_run_research_executes_and_combines_all_stages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = ResearchPlan(
        sub_questions=["What is happening?", "What causes it?", "What are effects?"],
        scope_boundaries=["Use recent findings."],
        recommended_source_types=["Research papers"],
    )
    evidence_by_query = {
        query: [make_evidence(query, f"E-{index}")]
        for index, query in enumerate(plan.sub_questions, start=1)
    }
    claim = ResearchClaim(
        claim_id="C-001",
        claim_text="A verifiable finding.",
        evidence_ids=["E-1"],
        status="unverified",
    )
    verified = VerifiedClaim(
        claim=claim.model_copy(update={"status": "supported"}),
        verification=VerificationRecord(
            claim_id="C-001",
            verdict="supported",
            rationale="The cited passage supports the claim.",
            evidence_ids=["E-1"],
            checked_at=datetime.now(timezone.utc),
        ),
    )
    calls = []
    persisted = []

    def fake_plan(question: str) -> ResearchPlan:
        calls.append(("plan", question))
        return plan

    def fake_search(query: str, count: int) -> list[EvidenceRecord]:
        calls.append(("search", query, count))
        return evidence_by_query[query]

    def fake_save(records: list[EvidenceRecord]) -> None:
        calls.append(("persist", len(records)))
        persisted.extend(records)

    def fake_draft(
        question: str,
        evidence: list[EvidenceRecord],
    ) -> list[ResearchClaim]:
        calls.append(("draft", question, len(evidence)))
        return [claim]

    def fake_verify(
        claims: list[ResearchClaim],
        evidence: list[EvidenceRecord],
    ) -> list[VerifiedClaim]:
        calls.append(("verify", len(claims), len(evidence)))
        return [verified]

    monkeypatch.setattr(research_workflow, "create_research_plan", fake_plan)
    monkeypatch.setattr(research_workflow, "search_sources", fake_search)
    monkeypatch.setattr(research_workflow, "save_evidence", fake_save)
    monkeypatch.setattr(research_workflow, "draft_claims", fake_draft)
    monkeypatch.setattr(research_workflow, "verify_claims", fake_verify)

    result = research_workflow.run_research("Research this", results_per_query=2)

    assert isinstance(result, ResearchRunResponse)
    assert result.question == "Research this"
    assert result.plan == plan
    assert result.evidence == [record for items in evidence_by_query.values() for record in items]
    assert result.claims == [claim]
    assert result.verifications == [verified]
    assert persisted == result.evidence
    assert calls == [
        ("plan", "Research this"),
        ("search", "What is happening?", 2),
        ("search", "What causes it?", 2),
        ("search", "What are effects?", 2),
        ("persist", 3),
        ("draft", "Research this", 3),
        ("verify", 1, 3),
    ]


def test_run_research_does_not_persist_partial_search_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = ResearchPlan(
        sub_questions=["What is happening?", "What causes it?", "What are effects?"],
        scope_boundaries=["Use recent findings."],
        recommended_source_types=["Research papers"],
    )
    monkeypatch.setattr(research_workflow, "create_research_plan", lambda _: plan)
    searches = iter(
        [
            [make_evidence(plan.sub_questions[0], "E-1")],
            RuntimeError("Search provider failed."),
        ]
    )

    def fake_search(query: str, count: int) -> list[EvidenceRecord]:
        result = next(searches)
        if isinstance(result, Exception):
            raise result
        return result

    persisted = []
    monkeypatch.setattr(research_workflow, "search_sources", fake_search)
    monkeypatch.setattr(
        research_workflow,
        "save_evidence",
        lambda records: persisted.extend(records),
    )

    with pytest.raises(RuntimeError, match="Search provider failed"):
        research_workflow.run_research("Research this")

    assert persisted == []
