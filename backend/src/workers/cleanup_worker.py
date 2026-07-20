import asyncio
import signal

from sqlalchemy import select

from src.core.database import AsyncSessionLocal
from src.documents.click_event import ClickEvent
from src.log_utils import get_logger, setup_logging
from src.models.url import URL, URLStatus
from src.repositories import AnalyticsRepository, URLRepository


async def run_cleanup(logger, db):
    url_repo = URLRepository(db)

    result = await db.execute(
        select(URL.id, URL.short_code).where(URL.status == URLStatus.deleted)
    )
    deleted_rows = result.all()

    if not deleted_rows:
        return

    logger.info("Found %d soft-deleted URLs to purge.", len(deleted_rows))
    url_ids = [row.id for row in deleted_rows]

    try:
        short_codes = [row.short_code for row in deleted_rows]
        await ClickEvent.find({"short_code": {"$in": short_codes}}).delete()
    except Exception as e:
        logger.warning("Failed to purge MongoDB events: %s", str(e))

    analytics_repo = AnalyticsRepository(db)
    await analytics_repo.delete_by_url_ids(url_ids)

    for url_id in url_ids:
        await url_repo.delete(url_id)

    logger.info("Cleanup purge complete. Removed %d URL(s).", len(url_ids))


async def start_worker():
    setup_logging()
    from src.core.tracing import init_metrics, init_tracing
    init_tracing()
    init_metrics()
    logger = get_logger("cleanup-worker")
    logger.info("Cleanup Worker started")
    interval = 45
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
            async with AsyncSessionLocal() as db:
                await run_cleanup(logger, db)
        except Exception as e:
            logger.warning("Error in cleanup loop: %s", str(e))
        await asyncio.sleep(interval)

    logger.info("Cleanup Worker stopped")


if __name__ == "__main__":
    asyncio.run(start_worker())
