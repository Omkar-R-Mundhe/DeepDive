from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.agents import report_writer
from app.schemas.research import (
    EvidenceRecord,
    ResearchClaim,
    VerifiedClaim,
    VerificationRecord,
)


def make_verified_claim(evidence_id: str = "E-1") -> VerifiedClaim:
    claim = ResearchClaim(
        claim_id="C-1",
        claim_text="A supported finding.",
        evidence_ids=[evidence_id],
        status="supported",
    )
    return VerifiedClaim(
        claim=claim,
        verification=VerificationRecord(
            claim_id=claim.claim_id,
            verdict="supported",
            rationale="The passage directly states this finding.",
            evidence_ids=[evidence_id],
            checked_at=datetime.now(timezone.utc),
        ),
    )


def make_evidence(evidence_id: str = "E-1") -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        query="Research question",
        source_url=f"https://example.org/{evidence_id}",
        source_title="Research source",
        retrieved_at=datetime.now(timezone.utc),
        passage="A source passage supporting the finding.",
    )


def test_write_research_report_returns_grounded_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_response = '{"answer":"The evidence supports the finding.","sections":[{"heading":"Finding","body":"The source states the finding.","evidence_ids":["E-1"]}]}'
    ask_model = Mock(return_value=client_response)
    monkeypatch.setattr(report_writer, "ask_model", ask_model)

    report = report_writer.write_research_report(
        "Research question",
        [make_verified_claim()],
        [make_evidence()],
    )

    assert report.answer == "The evidence supports the finding."
    assert report.sections[0].evidence_ids == ["E-1"]
    prompt = ask_model.call_args.args[0]
    assert "supported" in prompt
    assert "A source passage supporting the finding." in prompt


def test_write_research_report_rejects_unverified_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        report_writer,
        "ask_model",
        lambda _: (
            '{"answer":"A finding.","sections":[{"heading":"Finding",'
            '"body":"A finding.","evidence_ids":["E-unknown"]}]}'
        ),
    )

    with pytest.raises(report_writer.ResearchReportError, match="not selected"):
        report_writer.write_research_report(
            "Research question",
            [make_verified_claim()],
            [make_evidence()],
        )


def test_write_research_report_requires_citations_when_verified_evidence_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        report_writer,
        "ask_model",
        lambda _: (
            '{"answer":"A finding.","sections":[{"heading":"Finding",'
            '"body":"A finding.","evidence_ids":[]}]}'
        ),
    )

    with pytest.raises(report_writer.ResearchReportError, match="without a verified"):
        report_writer.write_research_report(
            "Research question",
            [make_verified_claim()],
            [make_evidence()],
        )


def test_write_research_report_rejects_malformed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(report_writer, "ask_model", lambda _: "not JSON")

    with pytest.raises(report_writer.ResearchReportError, match="invalid structured"):
        report_writer.write_research_report(
            "Research question",
            [make_verified_claim()],
            [make_evidence()],
        )
