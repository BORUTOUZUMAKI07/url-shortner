from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.core.base import Base


class DeadLetterEvent(Base):
    __tablename__ = "dead_letter_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    topic: Mapped[str] = mapped_column(String, nullable=False)
    event_key: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str] = mapped_column(String, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
