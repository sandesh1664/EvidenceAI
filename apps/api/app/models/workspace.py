import uuid
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, IdentityMixin, TimestampMixin


class Workspace(IdentityMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"
    name: Mapped[str] = mapped_column(String(200))
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    owner: Mapped["User"] = relationship(back_populates="owned_workspaces")
    members: Mapped[list["WorkspaceMember"]] = relationship(back_populates="workspace", passive_deletes="all")
    documents: Mapped[list["Document"]] = relationship(back_populates="workspace", passive_deletes="all")
