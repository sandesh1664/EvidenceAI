import uuid
from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, IdentityMixin, TimestampMixin


class DocumentChunk(IdentityMixin, TimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        ForeignKeyConstraint(["document_id", "workspace_id"], ["documents.id", "documents.workspace_id"],
                             ondelete="RESTRICT", name="fk_document_chunks_document_workspace"),
        UniqueConstraint("document_id", "chunk_index"),
        CheckConstraint("chunk_index >= 0", name="nonnegative_index"),
        CheckConstraint("char_start >= 0 AND char_end > char_start", name="valid_offsets"),
        CheckConstraint("page_number IS NULL OR page_number > 0", name="positive_page"),
        CheckConstraint("length(text) > 0", name="nonempty_text"),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(200))
    source_ref: Mapped[str] = mapped_column(String(200))
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
