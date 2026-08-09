import asyncio
import traceback
from datetime import datetime, timedelta, timezone

from src.analytics.repositories import AnalyticsRepository
from src.links.repositories import URLRepository
from src.shared import get_logger, setup_logging
from src.shared.core.click_event import ClickEvent
from src.shared.core.database import AsyncSessionLocal
from src.shared.core.mongodb import init_mongodb
from src.shared.core.redis import redis_client
from src.shared.workers.shutdown import install_signal_handlers, wait_for_shutdown

_CUTOFF_KEY = "aggregation:last_cutoff"
_last_cutoff: datetime | None = None


async def _load_cutoff() -> datetime | None:
    global _last_cutoff
    if _last_cutoff is not None:
        return _last_cutoff
    try:
        raw = await redis_client.get(_CUTOFF_KEY)
        if raw:
            _last_cutoff = datetime.fromisoformat(raw)
    except Exception:
        pass
    return _last_cutoff


async def _save_cutoff(cutoff: datetime) -> None:
    global _last_cutoff
    _last_cutoff = cutoff
    try:
        await redis_client.setex(_CUTOFF_KEY, 90 * 86400, cutoff.isoformat())
    except Exception:
        pass


async def run_aggregation_rollup(logger):
    match: dict[str, object] = {}
    cutoff = await _load_cutoff()
    if cutoff:
        match["clicked_at"] = {"$gt": cutoff}
    pipeline: list[dict[str, object]] = []
    if match:
        pipeline.append({"$match": match})
    pipeline.extend([
        {"$group": {
            "_id": "$short_code",
            "unique_ips": {"$addToSet": "$ip_address"},
            "total_clicks": {"$sum": 1},
            "max_clicked_at": {"$max": "$clicked_at"},
        }},
        {"$project": {
            "short_code": "$_id",
            "unique_clicks": {"$size": "$unique_ips"},
            "total_clicks": "$total_clicks",
            "max_clicked_at": 1,
        }},
    ])

    try:
        mongo_results = await ClickEvent.aggregate(pipeline).to_list()
    except Exception as e:
        logger.error("Failed to aggregate MongoDB events: %s\n%s", str(e), traceback.format_exc())
        return

    if not mongo_results:
        await _save_cutoff(datetime.now(timezone.utc) - timedelta(seconds=1))
        return

    async with AsyncSessionLocal() as db:
        url_repo = URLRepository(db)
        analytics_repo = AnalyticsRepository(db)
        updated_count = 0

        for item in mongo_results:
            short_code = item["short_code"]
            url_id = await url_repo.get_url_id_by_short_code(short_code)
            if not url_id:
                continue
            await analytics_repo.upsert_rollup(url_id, item["total_clicks"], item["unique_clicks"])
            updated_count += 1

        logger.info("Rolled up %d analytics summaries.", updated_count)

    # Persist the watermark ONLY after the DB writes succeed. The cutoff is the
    # newest clicked_at among the events that were actually aggregated, so a
    # crash between aggregation and persistence re-runs the same window instead
    # of permanently dropping it (the old code saved a wall-clock cutoff BEFORE
    # writing, so a crash lost that window forever).
    window_max = max(item["max_clicked_at"] for item in mongo_results)
    if window_max.tzinfo is None:
        window_max = window_max.replace(tzinfo=timezone.utc)
    await _save_cutoff(window_max)


async def start_worker():
    setup_logging()
    from src.shared.core.tracing import init_metrics, init_tracing
    init_tracing()
    init_metrics()
    logger = get_logger("aggregation-worker")
    logger.info("Aggregation Worker started")
    try:
        await init_mongodb()
        logger.info("MongoDB initialized")
    except Exception as e:
        logger.warning("MongoDB connection failed (aggregation will retry): %s", str(e))
    interval = 60
    install_signal_handlers()

    while not await wait_for_shutdown():
        try:
            await run_aggregation_rollup(logger)
        except Exception as e:
            logger.warning("Error in aggregation loop: %s", str(e))
        try:
            await asyncio.wait_for(asyncio.shield(wait_for_shutdown()), timeout=interval)
        except asyncio.TimeoutError:
            pass

    logger.info("Aggregation Worker stopped")


if __name__ == "__main__":
    asyncio.run(start_worker())
