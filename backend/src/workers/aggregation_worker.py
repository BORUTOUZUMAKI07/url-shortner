import asyncio
import signal
import traceback
from datetime import datetime, timedelta, timezone

from src.core.database import AsyncSessionLocal
from src.core.mongodb import init_mongodb
from src.documents.click_event import ClickEvent
from src.log_utils import get_logger, setup_logging
from src.repositories import AnalyticsRepository, URLRepository

_last_cutoff: datetime | None = None


async def run_aggregation_rollup(logger):
    global _last_cutoff
    match: dict[str, object] = {}
    if _last_cutoff:
        match["clicked_at"] = {"$gt": _last_cutoff}
    pipeline: list[dict[str, object]] = []
    if match:
        pipeline.append({"$match": match})
    pipeline.extend([
        {"$group": {
            "_id": "$short_code",
            "unique_ips": {"$addToSet": "$ip_address"},
            "total_clicks": {"$sum": 1},
        }},
        {"$project": {
            "short_code": "$_id",
            "unique_clicks": {"$size": "$unique_ips"},
            "total_clicks": "$total_clicks",
        }},
    ])

    try:
        mongo_results = await ClickEvent.aggregate(pipeline).to_list()
    except Exception as e:
        logger.error("Failed to aggregate MongoDB events: %s\n%s", str(e), traceback.format_exc())
        return

    if not mongo_results:
        _last_cutoff = datetime.now(timezone.utc) - timedelta(seconds=1)
        return

    _last_cutoff = datetime.now(timezone.utc) - timedelta(seconds=1)

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


async def start_worker():
    setup_logging()
    from src.core.tracing import init_metrics, init_tracing
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
    loop = asyncio.get_event_loop()
    stop = asyncio.Event()

    for sig_name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            try:
                loop.add_signal_handler(sig, stop.set)
            except NotImplementedError:
                pass

    while not stop.is_set():
        try:
            await run_aggregation_rollup(logger)
        except Exception as e:
            logger.warning("Error in aggregation loop: %s", str(e))
        await asyncio.sleep(interval)

    logger.info("Aggregation Worker stopped")


if __name__ == "__main__":
    asyncio.run(start_worker())
