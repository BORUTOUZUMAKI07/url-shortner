from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.core.base import Base


class URLAnalyticsSummary(Base):
    __tablename__ = "url_analytics_summary"

    url_id: Mapped[int] = mapped_column(ForeignKey("urls.id", ondelete="CASCADE"), primary_key=True)
    total_clicks: Mapped[int] = mapped_column(Integer, default=0)
    unique_clicks: Mapped[int] = mapped_column(Integer, default=0)
    last_clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    url = relationship("URL", backref="analytics")
