from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
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


class AggregationWatermark(Base):
    """Cursor for the analytics rollup worker, stored in Postgres.

    This used to live only in Redis, which made it impossible to advance the
    cursor atomically with the rollup it describes. `upsert_rollup` ADDS to the
    counters, so a window applied without its cursor advancing is applied again
    on the next cycle and the totals inflate permanently. Redis is a different
    store from the one holding the counters, so no ordering of two writes to
    them is safe.

    Keeping the cursor in the same database, updated in the same transaction,
    makes "rollup and advance" one indivisible step. Redis is now only a cache
    of this row.
    """

    __tablename__ = "aggregation_watermarks"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
