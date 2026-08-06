from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from src.analytics.models.analytics import URLAnalyticsSummary
from src.shared.core.base_repository import BaseRepository


class AnalyticsRepository(BaseRepository[URLAnalyticsSummary]):
    def __init__(self, db):
        super().__init__(URLAnalyticsSummary, db)

    async def get_by_url_id(self, url_id: int) -> URLAnalyticsSummary | None:
        return await self.get(url_id)

    async def upsert_click(self, url_id: int, clicked_at, is_unique: bool = True) -> None:
        stmt = insert(URLAnalyticsSummary).values(
            url_id=url_id, total_clicks=1, unique_clicks=1, last_clicked_at=clicked_at
        )
        update_dict = {
            "total_clicks": URLAnalyticsSummary.total_clicks + 1,
            "last_clicked_at": clicked_at,
        }
        if is_unique:
            update_dict["unique_clicks"] = URLAnalyticsSummary.unique_clicks + 1
        stmt = stmt.on_conflict_do_update(
            index_elements=["url_id"],
            set_=update_dict,
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def upsert_rollup(self, url_id: int, total_clicks: int, unique_clicks: int) -> None:
        stmt = insert(URLAnalyticsSummary).values(
            url_id=url_id, total_clicks=total_clicks, unique_clicks=unique_clicks
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["url_id"],
            set_={"total_clicks": total_clicks, "unique_clicks": unique_clicks},
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
