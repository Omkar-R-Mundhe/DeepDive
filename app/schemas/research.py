from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ResearchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    sub_questions: list[str] = Field(min_length=3, max_length=5)
    scope_boundaries: list[str] = Field(min_length=1)
    recommended_source_types: list[str] = Field(min_length=1)

    @field_validator(
        "sub_questions",
        "scope_boundaries",
        "recommended_source_types",
    )
    @classmethod
    def reject_blank_entries(cls, values: list[str]) -> list[str]:
        if any(not value for value in values):
            raise ValueError("Entries must not be blank.")
        return values

    @field_validator("sub_questions")
    @classmethod
    def require_distinct_sub_questions(cls, values: list[str]) -> list[str]:
        normalized = [value.casefold() for value in values]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Sub-questions must be distinct.")
        return values


class SearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1)
    count: int = Field(default=5, ge=1, le=10)


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    evidence_id: str
    query: str
    source_url: str
    source_title: str
    retrieved_at: datetime
    passage: str
    source_type: Literal["search_snippet"] = "search_snippet"


class SearchResponse(BaseModel):
    query: str
    evidence: list[EvidenceRecord]


class ClaimDraftItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    claim_text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(max_length=20)

    @field_validator("evidence_ids")
    @classmethod
    def require_unique_evidence_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Evidence IDs must be unique.")
        return values


class ClaimDraftBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[ClaimDraftItem] = Field(min_length=1, max_length=20)

    @field_validator("claims")
    @classmethod
    def require_unique_claims(
        cls,
        values: list[ClaimDraftItem],
    ) -> list[ClaimDraftItem]:
        normalized = [claim.claim_text.casefold() for claim in values]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Claims must be distinct.")
        return values


class ResearchClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    claim_id: str = Field(default_factory=lambda: f"C-{uuid4().hex[:12]}")
    claim_text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(max_length=20)
    status: Literal[
        "needs_evidence",
        "unverified",
        "supported",
        "contradicted",
        "insufficient_evidence",
    ]

    @field_validator("evidence_ids")
    @classmethod
    def require_unique_evidence_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Evidence IDs must be unique.")
        return values


class ClaimDraftRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1)
    evidence: list[EvidenceRecord] = Field(min_length=1, max_length=50)

    @field_validator("evidence")
    @classmethod
    def require_unique_evidence_records(
        cls,
        values: list[EvidenceRecord],
    ) -> list[EvidenceRecord]:
        evidence_ids = [record.evidence_id for record in values]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Evidence IDs must be unique.")
        return values


class ClaimDraftResponse(BaseModel):
    claims: list[ResearchClaim]


class VerificationVerdictItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    claim_id: str = Field(min_length=1)
    verdict: Literal["supported", "contradicted", "insufficient_evidence"]
    rationale: str = Field(min_length=1)
    evidence_ids: list[str] = Field(max_length=20)

    @field_validator("evidence_ids")
    @classmethod
    def require_unique_evidence_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Evidence IDs must be unique.")
        return values

    @model_validator(mode="after")
    def require_evidence_for_definitive_verdict(self) -> "VerificationVerdictItem":
        if self.verdict != "insufficient_evidence" and not self.evidence_ids:
            raise ValueError("Definitive verdicts must cite evidence.")
        return self


class VerificationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verifications: list[VerificationVerdictItem] = Field(min_length=1, max_length=20)

    @field_validator("verifications")
    @classmethod
    def require_unique_claim_ids(
        cls,
        values: list[VerificationVerdictItem],
    ) -> list[VerificationVerdictItem]:
        claim_ids = [item.claim_id for item in values]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("Each claim must have exactly one verification.")
        return values


class ClaimVerificationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    claims: list[ResearchClaim] = Field(min_length=1, max_length=20)
    evidence: list[EvidenceRecord] = Field(max_length=50)

    @field_validator("evidence")
    @classmethod
    def require_unique_evidence_records(
        cls,
        values: list[EvidenceRecord],
    ) -> list[EvidenceRecord]:
        evidence_ids = [record.evidence_id for record in values]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Evidence IDs must be unique.")
        return values


class VerificationRecord(BaseModel):
    claim_id: str
    verdict: Literal["supported", "contradicted", "insufficient_evidence"]
    rationale: str
    evidence_ids: list[str]
    checked_at: datetime


class VerifiedClaim(BaseModel):
    claim: ResearchClaim
    verification: VerificationRecord


class ClaimVerificationResponse(BaseModel):
    verifications: list[VerifiedClaim]


class ResearchRunRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1)
    results_per_query: int = Field(default=3, ge=1, le=5)


class ResearchRunResponse(BaseModel):
    question: str
    plan: ResearchPlan
    evidence: list[EvidenceRecord]
    claims: list[ResearchClaim]
    verifications: list[VerifiedClaim]
