"""Private conversations, durable ordered turns and bounded citation snapshots."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdentityMixin, TimestampMixin


class Conversation(IdentityMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint("length(btrim(title)) BETWEEN 1 AND 200", name="valid_title"),
        CheckConstraint(
            "next_sequence >= 1 AND mod(next_sequence, 2) = 1", name="valid_sequence"
        ),
        Index(
            "ix_conversations_owner_created",
            "workspace_id",
            "owner_id",
            "created_at",
            "id",
        ),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT")
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(200))
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_sequence: Mapped[int] = mapped_column(Integer, server_default="1", default=1)


class Message(IdentityMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "sequence", name="uq_messages_conversation_sequence"
        ),
        UniqueConstraint(
            "conversation_id", "idempotency_key", name="uq_messages_conversation_key"
        ),
        CheckConstraint("role IN ('user','assistant')", name="valid_role"),
        CheckConstraint(
            "generation_status IN ('pending','completed','failed')",
            name="valid_generation_status",
        ),
        CheckConstraint(
            "answer_status IS NULL OR answer_status IN ('answered','insufficient_evidence','retrieval_unavailable','provider_error')",
            name="valid_answer_status",
        ),
        CheckConstraint("sequence > 0", name="positive_sequence"),
        CheckConstraint(
            "(role = 'user' AND mod(sequence, 2) = 1 AND generation_status = 'completed' AND length(content) > 0 AND idempotency_key IS NOT NULL AND request_fingerprint IS NOT NULL AND answer_status IS NULL AND lease_expires_at IS NULL) OR (role = 'assistant' AND mod(sequence, 2) = 0 AND idempotency_key IS NULL AND request_fingerprint IS NULL)",
            name="role_fields",
        ),
        CheckConstraint(
            "role != 'assistant' OR (generation_status = 'pending' AND answer_status IS NULL AND content = '' AND lease_expires_at IS NOT NULL) OR (generation_status != 'pending' AND answer_status IS NOT NULL AND length(content) > 0 AND lease_expires_at IS NULL)",
            name="terminal_fields",
        ),
        Index(
            "ix_messages_one_pending",
            "conversation_id",
            unique=True,
            postgresql_where=text("generation_status = 'pending'"),
        ),
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    sequence: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    generation_status: Mapped[str] = mapped_column(String(16))
    answer_status: Mapped[str | None] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(String(80))
    model_identifier: Mapped[str | None] = mapped_column(String(240))
    usage: Mapped[dict | None] = mapped_column(JSONB)
    claims: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    retrieved_evidence_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    request_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    generation_http_status: Mapped[int | None] = mapped_column(Integer)
    idempotency_key: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    request_fingerprint: Mapped[str | None] = mapped_column(String(64))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MessageCitation(IdentityMixin, Base):
    __tablename__ = "message_citations"
    __table_args__ = (
        UniqueConstraint(
            "message_id", "citation_id", name="uq_message_citations_identifier"
        ),
        UniqueConstraint(
            "message_id", "ordering", name="uq_message_citations_ordering"
        ),
        CheckConstraint("ordering >= 0", name="nonnegative_ordering"),
        CheckConstraint(
            "char_start >= 0 AND char_end > char_start", name="valid_offsets"
        ),
        CheckConstraint("citation_id ~ '^C[1-9][0-9]?$'", name="valid_identifier"),
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE")
    )
    # Nullable live links. Immutable source IDs and bounded snapshots survive deletion.
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), index=True
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"), index=True
    )
    original_document_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    original_chunk_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    citation_id: Mapped[str] = mapped_column(String(4))
    supporting_excerpt: Mapped[str] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(String(1024))
    page_number: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(200))
    source_ref: Mapped[str] = mapped_column(String(200))
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    ordering: Mapped[int] = mapped_column(Integer)
    validation_metadata: Mapped[dict] = mapped_column(JSONB)
