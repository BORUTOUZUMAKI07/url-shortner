import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from src.shared.core.base import Base


class APIKeyStatus(str, enum.Enum):
    active = "active"
    revoked = "revoked"


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(100), nullable=False)       # human-readable label
    prefix: Mapped[str] = mapped_column(String(8), nullable=False)        # first 8 chars shown in UI
    key_hash: Mapped[str] = mapped_column(String, nullable=False)          # Argon2id hash of the full key
    status: Mapped[APIKeyStatus] = mapped_column(Enum(APIKeyStatus), default=APIKeyStatus.active)

    # Quota tracking — reset daily via Redis
    daily_requests_used: Mapped[int] = mapped_column(Integer, default=0)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", backref=backref("api_keys", passive_deletes=True))
