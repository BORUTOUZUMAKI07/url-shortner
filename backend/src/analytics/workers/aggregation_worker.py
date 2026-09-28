import asyncio
import time
import traceback
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from src.analytics.repositories import AnalyticsRepository
from src.links.models.url import URL, URLStatus
from src.links.repositories import URLRepository
from src.shared import get_logger, setup_logging
from src.shared.core.click_event import ClickEvent
from src.shared.core.database import AsyncSessionLocal
from src.shared.core.mongodb import init_mongodb
from src.shared.core.redis import redis_client
from src.shared.workers.shutdown import install_signal_handlers, wait_for_shutdown

_CUTOFF_KEY = "aggregation:last_cutoff"
# Row key in the `aggregation_watermarks` table. Postgres is authoritative;
# _CUTOFF_KEY in Redis is a cache of it.
_WATERMARK_KEY = "url_clicked_rollup"
_last_cutoff: datetime | None = None

# Soft-delete → hard-delete housekeeping (formerly the cleanup_worker).
# Runs once per hour inside this process instead of a dedicated poller.
_PURGE_INTERVAL = 3600          # seconds between purge runs
_PURGE_STALE_SECONDS = 30 * 86400  # 30-day grace period
_last_purge_ts: float = 0.0


async def _load_cutoff() -> datetime | None:
    """Read the watermark from Postgres, which is the source of truth.

    The Redis copy is a cache of that row, so falling back to it only matters
    for a database that predates the watermark table. Reading one primary-key
    row once per 60s cycle costs nothing.
    """
    global _last_cutoff
    if _last_cutoff is not None:
        return _last_cutoff
    try:
        async with AsyncSessionLocal() as db:
            stored = await AnalyticsRepository(db).get_watermark(_WATERMARK_KEY)
        if stored is not None:
            _last_cutoff = stored
            return _last_cutoff
    except Exception:
        pass
    # Fallback: the pre-migration Redis cursor.
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

    window_max = max(item["max_clicked_at"] for item in mongo_results)
    if window_max.tzinfo is None:
        window_max = window_max.replace(tzinfo=timezone.utc)

    async with AsyncSessionLocal() as db:
        url_repo = URLRepository(db)
        analytics_repo = AnalyticsRepository(db)

        # One query for the whole window, not one per short code.
        url_ids = await url_repo.get_url_ids_by_short_codes(
            [item["short_code"] for item in mongo_results]
        )

        updated_count = 0
        for item in mongo_results:
            url_id = url_ids.get(item["short_code"])
            if not url_id:
                continue
            await analytics_repo.upsert_rollup(url_id, item["total_clicks"], item["unique_clicks"])
            updated_count += 1

        # The watermark is written in the SAME transaction as the rollups above,
        # and this is the only commit.
        #
        # upsert_rollup ADDS to the counters, so a window that is applied but
        # whose cursor does not advance is applied a second time next cycle and
        # the totals inflate permanently, with no way to detect the replay. The
        # previous code committed per row and saved the watermark afterwards, to
        # a different store (Redis), so any failure between the first row and
        # the save left a partially-applied window that would be re-applied in
        # full. Now either the whole window and its cursor land together, or
        # neither does and the next cycle simply re-reads the same window.
        await analytics_repo.set_watermark(_WATERMARK_KEY, window_max)
        await db.commit()

        logger.info("Rolled up %d analytics summaries.", updated_count)

    # Redis is now only a cache of the Postgres watermark, refreshed after the
    # commit above. It is no longer load-bearing for correctness.
    await _save_cutoff(window_max)


async def run_purge_soft_deleted(logger):
    """Chunked hard-delete of soft-deleted URLs older than the grace period.

    This was previously a standalone cleanup_worker.  Folding it here avoids an
    always-on process for work that only needs to happen once an hour.
    The URL model has no `updated_at`, so we use `created_at` to derive the
    grace cutoff (a URL created > 30 days ago and currently soft-deleted is safe
    to hard-delete).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=_PURGE_STALE_SECONDS)
    async with AsyncSessionLocal() as db:
        url_repo = URLRepository(db)
        analytics_repo = AnalyticsRepository(db)

        while True:
            result = await db.execute(
                select(URL.id, URL.short_code)
                .where(URL.status == URLStatus.deleted, URL.created_at < cutoff)
                .limit(500)
            )
            rows = result.all()
            if not rows:
                break

            url_ids = [row.id for row in rows]
            short_codes = [row.short_code for row in rows]
            logger.info("Purging %d soft-deleted URLs (chunk).", len(rows))

            try:
                await ClickEvent.find({"short_code": {"$in": short_codes}}).delete()
            except Exception as e:
                logger.warning("Failed to purge MongoDB events: %s", str(e))

            await analytics_repo.delete_by_url_ids(url_ids)
            for url_id in url_ids:
                await url_repo.delete(url_id)

    logger.info("Soft-delete purge complete.")


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

        # Hourly purge of stale soft-deleted URLs (replaces cleanup_worker).
        global _last_purge_ts
        if time.monotonic() - _last_purge_ts >= _PURGE_INTERVAL:
            try:
                await run_purge_soft_deleted(logger)
                _last_purge_ts = time.monotonic()
            except Exception as e:
                logger.warning("Error in purge loop: %s", str(e))

        try:
            await asyncio.wait_for(asyncio.shield(wait_for_shutdown()), timeout=interval)
        except asyncio.TimeoutError:
            pass

    logger.info("Aggregation Worker stopped")


if __name__ == "__main__":
    asyncio.run(start_worker())
