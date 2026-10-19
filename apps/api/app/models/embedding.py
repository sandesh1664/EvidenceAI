from datetime import datetime
import uuid
from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer,
                        String, Text, UniqueConstraint, Uuid, func)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class EmbeddingProfile(Base):
    __tablename__ = "embedding_profiles"
    __table_args__ = (
        UniqueConstraint("id", "dimensions"),
        CheckConstraint("dimensions >= 8 AND dimensions <= 3072", name="valid_dimensions"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(120))
    revision: Mapped[str] = mapped_column(String(80))
    dimensions: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        ForeignKeyConstraint(["profile_id","dimensions"], ["embedding_profiles.id","embedding_profiles.dimensions"],
                             ondelete="RESTRICT",name="fk_chunk_embeddings_profile_dimensions"),
        CheckConstraint("status IN ('pending','completed','failed')",name="valid_status"),
        CheckConstraint("vector IS NULL OR (vector_dims(vector) = dimensions AND vector_norm(vector) > 0)",name="valid_vector"),
        CheckConstraint("status != 'completed' OR (vector IS NOT NULL AND generated_at IS NOT NULL)",name="completed_vector"),
        Index("ix_chunk_embeddings_profile_status","profile_id","status"),
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_chunks.id",ondelete="CASCADE"),primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(64),primary_key=True)
    dimensions: Mapped[int] = mapped_column(Integer)
    vector: Mapped[list[float] | None] = mapped_column(VECTOR())
    generation: Mapped[uuid.UUID] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(String(16),default="pending",server_default="pending")
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class EmbeddingJob(TimestampMixin, Base):
    __tablename__ = "embedding_jobs"
    __table_args__ = (
        CheckConstraint("state IN ('queued','running','done','failed')",name="valid_state"),
        CheckConstraint("attempts >= 0",name="nonnegative_attempts"),
        Index("ix_embedding_jobs_profile_available","profile_id","available_at"),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id",ondelete="CASCADE"),primary_key=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("embedding_profiles.id",ondelete="RESTRICT"),primary_key=True)
    generation: Mapped[uuid.UUID] = mapped_column(Uuid)
    state: Mapped[str] = mapped_column(String(16),default="queued",server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer,default=0,server_default="0")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    lease_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
