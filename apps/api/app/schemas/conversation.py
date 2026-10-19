from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.ask import AnswerClaim, AskRequest, TokenUsage


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(
        default="New research conversation", min_length=1, max_length=200
    )

    @field_validator("title")
    @classmethod
    def valid_title(cls, value):
        if value is None:
            return value
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("Invalid title")
        return value


class ConversationUpdate(ConversationCreate):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    archived: bool | None = Field(default=None, strict=True)

    @model_validator(mode="after")
    def nonempty_update(self):
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError("Supply a non-null title or archived flag")
        return self


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    owner_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    archived_at: datetime | None


class ConversationPage(BaseModel):
    items: list[ConversationResponse]
    next_cursor: UUID | None


class MessageCreate(AskRequest):
    idempotency_key: UUID


class SavedCitation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    citation_id: str
    document_id: UUID | None
    chunk_id: UUID | None
    original_document_id: UUID
    original_chunk_id: UUID
    filename: str
    page_number: int | None
    section: str | None
    source_ref: str
    supporting_excerpt: str
    char_start: int
    char_end: int
    ordering: int
    validation_metadata: dict


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    conversation_id: UUID
    role: Literal["user", "assistant"]
    content: str
    sequence: int
    created_at: datetime
    generation_status: Literal["pending", "completed", "failed"]
    answer_status: (
        Literal[
            "answered",
            "insufficient_evidence",
            "retrieval_unavailable",
            "provider_error",
        ]
        | None
    )
    reason: str | None
    model_identifier: str | None
    usage: TokenUsage | None
    claims: list[AnswerClaim]
    retrieved_evidence_count: int
    request_id: UUID | None
    generation_http_status: int | None
    citations: list[SavedCitation] = Field(default_factory=list)


class MessagePage(BaseModel):
    items: list[MessageResponse]
    next_after_sequence: int | None


class TurnResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    replayed: bool
