import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.core.base import Base


class URLStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"
    deleted = "deleted"

class URL(Base):
    __tablename__ = "urls"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    short_code: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    original_url: Mapped[str] = mapped_column(String, nullable=False)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id", ondelete="SET NULL"), nullable=True)

    custom_alias: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    is_ab_test: Mapped[bool] = mapped_column(Boolean, default=False)
    is_one_time: Mapped[bool] = mapped_column(Boolean, default=False)   # disable after first click
    ios_url: Mapped[str | None] = mapped_column(String, nullable=True)
    android_url: Mapped[str | None] = mapped_column(String, nullable=True)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[URLStatus] = mapped_column(Enum(URLStatus), default=URLStatus.active)
    qr_code: Mapped[str | None] = mapped_column(String, nullable=True)  # base64-encoded PNG
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    og_image: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    folder = relationship("Folder", back_populates="urls")
    tags = relationship("Tag", secondary="url_tags", back_populates="urls")
