from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from src.analytics.models.analytics import URLAnalyticsSummary
from src.shared.core.base_repository import BaseRepository


class AnalyticsRepository(BaseRepository[URLAnalyticsSummary]):
    def __init__(self, db):
        super().__init__(URLAnalyticsSummary, db)

    async def get_by_url_id(self, url_id: int) -> URLAnalyticsSummary | None:
        return await self.get(url_id)

    async def upsert_click(self, url_id: int, clicked_at) -> None:
        # Realtime path only records the most recent click time. The click
        # counters are maintained by the aggregation worker (upsert_rollup) as
        # the single writer, otherwise the two paths double-count each click.
        stmt = insert(URLAnalyticsSummary).values(
            url_id=url_id, total_clicks=0, unique_clicks=0, last_clicked_at=clicked_at
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["url_id"],
            set_={"last_clicked_at": clicked_at},
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def upsert_rollup(self, url_id: int, total_clicks: int, unique_clicks: int) -> None:
        # The rollup only sees the events since the last cutoff (a window), so
        # the counters must be ADDED to the existing totals, never replaced —
        # replacing them would collapse the cumulative count to one window.
        stmt = insert(URLAnalyticsSummary).values(
            url_id=url_id, total_clicks=total_clicks, unique_clicks=unique_clicks
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["url_id"],
            set_={
                "total_clicks": URLAnalyticsSummary.total_clicks + total_clicks,
                "unique_clicks": URLAnalyticsSummary.unique_clicks + unique_clicks,
            },
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def delete_by_url_id(self, url_id: int) -> None:
        await self.db.execute(
            delete(URLAnalyticsSummary).where(URLAnalyticsSummary.url_id == url_id)
        )
        await self.db.commit()

    async def delete_by_url_ids(self, url_ids: list[int]) -> None:
        await self.db.execute(
            delete(URLAnalyticsSummary).where(URLAnalyticsSummary.url_id.in_(url_ids))
        )
        await self.db.commit()
