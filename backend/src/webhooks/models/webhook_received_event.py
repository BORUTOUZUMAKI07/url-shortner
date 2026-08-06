from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.core.base import Base


class WebhookReceivedEvent(Base):
    __tablename__ = "webhook_received_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    webhook_id: Mapped[int] = mapped_column(ForeignKey("webhooks.id", ondelete="SET NULL"), nullable=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    headers: Mapped[str] = mapped_column(Text, nullable=True)
    signature: Mapped[str | None] = mapped_column(String, nullable=True)
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    source_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
