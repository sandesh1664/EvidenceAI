from datetime import datetime
import uuid
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class DocumentJob(TimestampMixin, Base):
    __tablename__ = "document_jobs"
    __table_args__ = (CheckConstraint("state IN ('queued','running','done','failed')", name="valid_state"),)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"), primary_key=True)
    state: Mapped[str] = mapped_column(String(20), default="queued", server_default="queued", index=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    lease_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StorageCleanup(Base):
    __tablename__ = "storage_cleanup"
    storage_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String(200))
