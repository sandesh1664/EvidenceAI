from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[UUID] | None = Field(default=None, max_length=50)
    retrieval_limit: int | None = Field(default=None, ge=1, le=12, strict=True)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value):
        value = value.strip()
        if (
            not value
            or len(value.encode("utf-8")) > 6000
            or any(ord(c) < 32 and c not in "\n\t" for c in value)
        ):
            raise ValueError("Invalid question")
        return value

    @field_validator("document_ids")
    @classmethod
    def unique_filters(cls, value):
        if value is not None and len(value) != len(set(value)):
            raise ValueError("Document filters must be unique")
        return value


class StrictOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ModelSupport(StrictOutput):
    citation_id: str = Field(min_length=2, max_length=4, pattern=r"^C[1-9][0-9]?$")
    quote: str = Field(min_length=8, max_length=600)


class ModelClaim(StrictOutput):
    text: str = Field(min_length=8, max_length=600)
    supports: list[ModelSupport] = Field(min_length=1, max_length=4)


class GroundedOutput(StrictOutput):
    outcome: Literal["answered", "insufficient_evidence"]
    claims: list[ModelClaim] = Field(max_length=6)

    @model_validator(mode="after")
    def consistent_outcome(self):
        if (self.outcome == "answered") != bool(self.claims):
            raise ValueError("Outcome and claims disagree")
        return self


class TokenUsage(StrictOutput):
    input_tokens: int = Field(ge=0, le=10000000)
    output_tokens: int = Field(ge=0, le=10000000)
    total_tokens: int = Field(ge=0, le=20000000)

    @model_validator(mode="after")
    def total_matches(self):
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("Inconsistent provider usage")
        return self


class AnswerClaim(BaseModel):
    claim_id: str
    text: str
    citation_ids: list[str]


class Citation(BaseModel):
    citation_id: str
    document_id: UUID
    chunk_id: UUID
    filename: str
    page_number: int | None
    section: str | None
    source_ref: str
    supporting_excerpt: str
    char_start: int
    char_end: int
    claim_ids: list[str]


class AskResponse(BaseModel):
    answer: str
    status: Literal[
        "answered", "insufficient_evidence", "retrieval_unavailable", "provider_error"
    ]
    reason: str
    claims: list[AnswerClaim]
    citations: list[Citation]
    retrieved_evidence_count: int
    model_identifier: str | None
    usage: TokenUsage | None
    request_id: UUID
