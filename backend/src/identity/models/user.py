import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.core.base import Base


class PlanEnum(str, enum.Enum):
    free = "free"
    premium = "premium"
    enterprise = "enterprise"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # Soft kill switch. Checked on every authenticated request (deps.get_current_user
    # already loads the row), so deactivating a user takes effect immediately
    # instead of waiting out their access token. Previously users could only be
    # hard-deleted, which cascades away all their workspaces and audit links.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    plan: Mapped[PlanEnum] = mapped_column(Enum(PlanEnum), default=PlanEnum.free)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Avatar
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # OAuth fields. google_id/github_id are the provider's immutable subject
    # ("sub") and are the ONLY trustworthy link between an identity and a local
    # account - email is mutable at the provider and must never be used to
    # establish identity on its own. Each provider has its own column so
    # revoking or migrating one cannot collide with the other.
    google_id: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    github_id: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    oauth_provider: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g., 'google', 'github'
    oauth_avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    workspaces = relationship("Workspace", back_populates="owner", cascade="all, delete-orphan")
    workspace_memberships = relationship("WorkspaceMember", back_populates="user", cascade="all, delete-orphan")
