import pytest

from app.agents import verifier
from app.agents.verifier import ClaimVerificationError
from app.schemas.research import EvidenceRecord, ResearchClaim


def make_evidence() -> list[EvidenceRecord]:
    return [
        EvidenceRecord(
            evidence_id="E-001",
            query="urban trees and heat",
            source_url="https://example.org/canopy",
            source_title="City canopy study",
            retrieved_at="2026-10-12T16:00:00+00:00",
            passage="Neighborhoods with more canopy had lower average surface temperatures.",
        ),
        EvidenceRecord(
            evidence_id="E-002",
            query="urban trees and heat",
            source_url="https://example.org/other",
            source_title="An unrelated page",
            retrieved_at="2026-10-12T16:00:00+00:00",
            passage="The city's transit network expanded in 2022.",
        ),
    ]


def test_verify_claims_returns_supported_and_insufficient_verdicts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claims = [
        ResearchClaim(
            claim_id="C-001",
            claim_text="Higher canopy was associated with lower surface temperatures.",
            evidence_ids=["E-001"],
            status="unverified",
        ),
        ResearchClaim(
            claim_id="C-002",
            claim_text="Canopy reduced heat-related hospital admissions.",
            evidence_ids=["E-002"],
            status="unverified",
        ),
        ResearchClaim(
            claim_id="C-003",
            claim_text="An uncited claim.",
            evidence_ids=[],
            status="needs_evidence",
        ),
    ]
    prompts = []

    def fake_ask_model(prompt: str) -> str:
        prompts.append(prompt)
        return (
            '{"verifications":['
            '{"claim_id":"C-001","verdict":"supported",'
            '"rationale":"The passage directly reports lower surface temperatures.",'
            '"evidence_ids":["E-001"]},'
            '{"claim_id":"C-002","verdict":"insufficient_evidence",'
            '"rationale":"The passage does not mention hospital admissions.",'
            '"evidence_ids":[]}'
            ']}'
        )

    monkeypatch.setattr(verifier, "ask_model", fake_ask_model)

    results = verifier.verify_claims(claims, make_evidence())

    assert [item.verification.verdict for item in results] == [
        "supported",
        "insufficient_evidence",
        "insufficient_evidence",
    ]
    assert results[0].claim.status == "supported"
    assert results[1].claim.status == "insufficient_evidence"
    assert results[2].verification.rationale == "No evidence was cited for this claim."
    assert "untrusted data" in prompts[0]
    assert "The city's transit network expanded in 2022." in prompts[0]


def test_verify_claims_rejects_unknown_evidence_reference() -> None:
    claim = ResearchClaim(
        claim_id="C-001",
        claim_text="Claim requiring unknown evidence.",
        evidence_ids=["E-missing"],
        status="unverified",
    )

    with pytest.raises(ClaimVerificationError, match="was not supplied"):
        verifier.verify_claims([claim], make_evidence())


def test_verify_claims_rejects_model_citation_not_attached_to_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = ResearchClaim(
        claim_id="C-001",
        claim_text="The transit system expanded.",
        evidence_ids=["E-001"],
        status="unverified",
    )
    monkeypatch.setattr(
        verifier,
        "ask_model",
        lambda _: '{"verifications":[{"claim_id":"C-001",'
        '"verdict":"supported","rationale":"A reason.",'
        '"evidence_ids":["E-002"]}]}',
    )

    with pytest.raises(ClaimVerificationError, match="not attached"):
        verifier.verify_claims([claim], make_evidence())


def test_verify_claims_rejects_incomplete_verification_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claims = [
        ResearchClaim(
            claim_id=claim_id,
            claim_text=f"Claim {claim_id}.",
            evidence_ids=["E-001"],
            status="unverified",
        )
        for claim_id in ("C-001", "C-002")
    ]
    monkeypatch.setattr(
        verifier,
        "ask_model",
        lambda _: '{"verifications":[{"claim_id":"C-001",'
        '"verdict":"supported","rationale":"A reason.",'
        '"evidence_ids":["E-001"]}]}',
    )

    with pytest.raises(ClaimVerificationError, match="exactly one result"):
        verifier.verify_claims(claims, make_evidence())
