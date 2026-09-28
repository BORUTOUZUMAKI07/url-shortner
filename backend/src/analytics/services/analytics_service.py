import asyncio
from datetime import datetime, timedelta, timezone

from src.analytics.repositories.analytics_repository import AnalyticsRepository
from src.links.repositories.url_repository import URLRepository
from src.shared.core.click_event import ClickEvent
from src.shared.errors import ForbiddenError, URLNotFound
from src.workspaces.repositories.workspace_repository import WorkspaceRepository


class AnalyticsService:
    def __init__(self, url_repo: URLRepository, analytics_repo: AnalyticsRepository, workspace_repo: WorkspaceRepository):
        self.url_repo = url_repo
        self.analytics_repo = analytics_repo
        self.workspace_repo = workspace_repo

    async def _get_url_and_verify(self, short_code: str, user_id: int):
        url = await self.url_repo.get_by_short_code(short_code)
        if not url:
            raise URLNotFound()
        ws = await self.workspace_repo.verify_access(url.workspace_id, user_id)
        if not ws:
            raise ForbiddenError("You do not have access to this URL's analytics")
        return url

    async def get_summary(self, short_code: str, user_id: int, days: int = 7):
        """Totals for the same period the rest of the page is scoped to.

        This used to read `url_analytics_summary`, which holds all-time
        cumulative counters, and it took no `days` at all — the route never
        declared the parameter, so FastAPI discarded the `?days=` the frontend
        was already sending. The result was a page where the chart and every
        breakdown followed the period selector but the two stat cards did not:
        pick "24 hours" and the line chart shrank while "Total Clicks" stayed
        exactly where it was.

        Counted from ClickEvent for the same reason every other endpoint here
        is: that is where the per-event data lives. `url_analytics_summary` only
        keeps a 60s-rollup total (and a per-window sum of unique counts, which
        is an upper bound rather than a true distinct count), so it cannot answer
        a period-scoped question. One $facet keeps total, unique and last-click
        in a single round trip.
        """
        await self._get_url_and_verify(short_code, user_id)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        pipeline = [
            {"$match": {"short_code": short_code, "clicked_at": {"$gte": since}}},
            {
                "$facet": {
                    "total": [{"$count": "clicks"}],
                    "unique": [{"$group": {"_id": "$ip_address"}}],
                    "last": [{"$sort": {"clicked_at": -1}}, {"$limit": 1}],
                }
            },
        ]
        (result,) = await ClickEvent.aggregate(pipeline).to_list()

        total = result["total"][0]["clicks"] if result["total"] else 0
        last = result["last"][0]["clicked_at"] if result["last"] else None
        return {
            "short_code": short_code,
            "days": days,
            "total_clicks": total,
            # A true distinct count within the window, not the sum of per-window
            # counts the rollup keeps.
            "unique_clicks": len(result["unique"]),
            "last_clicked_at": last,
        }

    async def get_timeseries(self, short_code: str, user_id: int, days: int = 7):
        await self._get_url_and_verify(short_code, user_id)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        pipeline = [
            {"$match": {"short_code": short_code, "clicked_at": {"$gte": since}}},
            {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$clicked_at"}}, "clicks": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
        data = await ClickEvent.aggregate(pipeline).to_list()
        return {
            "short_code": short_code,
            "days": days,
            "data": [{"date": item["_id"], "clicks": item["clicks"]} for item in data],
        }

    async def get_device_breakdown(self, short_code: str, user_id: int, days: int = 7):
        await self._get_url_and_verify(short_code, user_id)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        match: dict[str, object] = {"short_code": short_code, "clicked_at": {"$gte": since}}

        def _group(field: str):
            return [
                {"$match": match},
                {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]

        geo_pipeline = [
            {"$match": {**match, "country": {"$ne": None}}},
            {"$group": {"_id": {"country": "$country", "city": "$city"}, "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]

        browsers, os_data, devices, geo = await asyncio.gather(
            ClickEvent.aggregate(_group("browser")).to_list(),
            ClickEvent.aggregate(_group("os")).to_list(),
            ClickEvent.aggregate(_group("device")).to_list(),
            ClickEvent.aggregate(geo_pipeline).to_list(),
        )

        return {
            "short_code": short_code,
            "days": days,
            "browsers": [{"name": item["_id"] or "Unknown", "count": item["count"]} for item in browsers],
            "os": [{"name": item["_id"] or "Unknown", "count": item["count"]} for item in os_data],
            "devices": [{"name": item["_id"] or "Unknown", "count": item["count"]} for item in devices],
            "geo": [{"country": item["_id"]["country"], "city": item["_id"]["city"], "count": item["count"]} for item in geo],
        }

    async def get_utm_breakdown(self, short_code: str, user_id: int, days: int = 7):
        await self._get_url_and_verify(short_code, user_id)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        pipeline = [
            {"$match": {"short_code": short_code, "clicked_at": {"$gte": since}, "utm_source": {"$ne": None}}},
            {"$group": {"_id": {"source": "$utm_source", "medium": "$utm_medium", "campaign": "$utm_campaign"}, "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 50},
        ]
        data = await ClickEvent.aggregate(pipeline).to_list()
        return {
            "short_code": short_code,
            "days": days,
            "data": [{
                "source": item["_id"]["source"],
                "medium": item["_id"]["medium"],
                "campaign": item["_id"]["campaign"],
                "count": item["count"],
            } for item in data],
        }

    async def get_referer_breakdown(self, short_code: str, user_id: int, days: int = 7):
        await self._get_url_and_verify(short_code, user_id)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        pipeline = [
            {"$match": {"short_code": short_code, "clicked_at": {"$gte": since}, "referer": {"$nin": [None, ""]}}},
            {"$group": {"_id": "$referer", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 50},
        ]
        data = await ClickEvent.aggregate(pipeline).to_list()
        return {
            "short_code": short_code,
            "days": days,
            "data": [{"referer": item["_id"], "count": item["count"]} for item in data],
        }
