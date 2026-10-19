from sqlalchemy import Boolean, String, Text, true, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, IdentityMixin, TimestampMixin


class User(IdentityMixin, TimestampMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    __table_args__ = (Index("uq_users_email_normalized", func.lower(func.btrim(email)), unique=True),)
    display_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    owned_workspaces: Mapped[list["Workspace"]] = relationship(back_populates="owner", passive_deletes="all")
    memberships: Mapped[list["WorkspaceMember"]] = relationship(back_populates="user", passive_deletes="all")
    documents: Mapped[list["Document"]] = relationship(back_populates="uploader", passive_deletes="all")
