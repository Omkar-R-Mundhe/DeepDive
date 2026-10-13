import pytest

from app.agents import claim_drafter
from app.agents.claim_drafter import ClaimDraftError
from app.schemas.research import EvidenceRecord


def make_evidence() -> list[EvidenceRecord]:
    return [
        EvidenceRecord(
            evidence_id="E-001",
            query="urban trees and heat",
            source_url="https://example.org/canopy",
            source_title="City canopy study",
            retrieved_at="2026-10-12T16:00:00+00:00",
            passage="Neighborhoods with more canopy had lower average surface temperatures.",
        )
    ]


def test_draft_claims_links_only_supplied_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_seen = []
    monkeypatch.setattr(
        claim_drafter,
        "ask_model",
        lambda prompt: prompt_seen.append(prompt)
        or '{"claims":[{"claim_text":"Higher canopy was associated with lower '
        'surface temperatures.","evidence_ids":["E-001"]}]}',
    )

    claims = claim_drafter.draft_claims("How does canopy relate to heat?", make_evidence())

    assert len(claims) == 1
    assert claims[0].claim_id.startswith("C-")
    assert claims[0].evidence_ids == ["E-001"]
    assert claims[0].status == "unverified"
    assert "untrusted source data" in prompt_seen[0]


def test_draft_claims_marks_claim_without_support_as_needing_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        claim_drafter,
        "ask_model",
        lambda _: '{"claims":[{"claim_text":"A related unresolved statement.",'
        '"evidence_ids":[]}]}',
    )

    claim = claim_drafter.draft_claims("Research this", make_evidence())[0]

    assert claim.status == "needs_evidence"
    assert claim.evidence_ids == []


def test_draft_claims_rejects_model_invented_evidence_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        claim_drafter,
        "ask_model",
        lambda _: '{"claims":[{"claim_text":"Unsupported attribution.",'
        '"evidence_ids":["E-unknown"]}]}',
    )

    with pytest.raises(ClaimDraftError, match="not supplied"):
        claim_drafter.draft_claims("Research this", make_evidence())


def test_draft_claims_accepts_json_wrapped_in_markdown_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        claim_drafter,
        "ask_model",
        lambda _: (
            '```json\n{"claims":[{"claim_text":"Canopy relates to heat.",'
            '"evidence_ids":["E-001"]}]}\n```'
        ),
    )

    claims = claim_drafter.draft_claims("Research this", make_evidence())

    assert claims[0].claim_text == "Canopy relates to heat."
    assert claims[0].evidence_ids == ["E-001"]


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ("", "empty response"),
        ("I cannot answer that.", "did not return a JSON object"),
    ],
)
def test_draft_claims_reports_non_json_model_response(
    monkeypatch: pytest.MonkeyPatch,
    response: str,
    message: str,
) -> None:
    monkeypatch.setattr(claim_drafter, "ask_model", lambda _: response)

    with pytest.raises(ClaimDraftError, match=message):
        claim_drafter.draft_claims("Research this", make_evidence())
