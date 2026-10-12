from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
