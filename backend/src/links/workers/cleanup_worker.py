import asyncio

from sqlalchemy import select

from src.analytics.repositories.analytics_repository import AnalyticsRepository
from src.links.models.url import URL, URLStatus
from src.links.repositories.url_repository import URLRepository
from src.shared import get_logger, setup_logging
from src.shared.core.click_event import ClickEvent
from src.shared.core.database import AsyncSessionLocal
from src.shared.workers.shutdown import install_signal_handlers, wait_for_shutdown


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
    from src.shared.core.tracing import init_metrics, init_tracing
    init_tracing()
    init_metrics()
    logger = get_logger("cleanup-worker")
    logger.info("Cleanup Worker started")
    interval = 45
    install_signal_handlers()

    while not await wait_for_shutdown():
        try:
            async with AsyncSessionLocal() as db:
                await run_cleanup(logger, db)
        except Exception as e:
            logger.warning("Error in cleanup loop: %s", str(e))
        try:
            await asyncio.wait_for(asyncio.shield(wait_for_shutdown()), timeout=interval)
        except asyncio.TimeoutError:
            pass

    logger.info("Cleanup Worker stopped")


if __name__ == "__main__":
    asyncio.run(start_worker())
