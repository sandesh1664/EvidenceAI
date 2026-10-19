import uuid
from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, IdentityMixin, TimestampMixin


class Document(IdentityMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("processing_status IN ('pending', 'processing', 'completed', 'failed')", name="valid_status"),
        CheckConstraint("file_size IS NULL OR file_size >= 0", name="nonnegative_file_size"),
        CheckConstraint("checksum_sha256 ~ '^[0-9a-f]{64}$'", name="valid_checksum"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    original_filename: Mapped[str] = mapped_column(String(1024))
    storage_key: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    processing_status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    processing_error: Mapped[str | None] = mapped_column(Text)
    workspace: Mapped["Workspace"] = relationship(back_populates="documents")
    uploader: Mapped["User"] = relationship(back_populates="documents")
