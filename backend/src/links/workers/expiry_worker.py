import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from src.links.models.url import URL, URLStatus
from src.links.repositories.url_repository import URLRepository
from src.shared import get_logger, setup_logging
from src.shared.core.database import AsyncSessionLocal
from src.shared.core.redis import delete_url_cache
from src.shared.workers.shutdown import install_signal_handlers, wait_for_shutdown


async def scan_and_expire_urls(logger):
    async with AsyncSessionLocal() as db:
        url_repo = URLRepository(db)
        result = await db.execute(
            select(URL).where(
                URL.status == URLStatus.active,
                URL.expires_at.isnot(None),
                URL.expires_at < datetime.now(timezone.utc),
            )
        )
        expired_urls = result.scalars().all()

        if not expired_urls:
            return

        logger.info("Found %d expired URLs to process.", len(expired_urls))
        for url in expired_urls:
            await url_repo.update(url.id, status=URLStatus.disabled)
            await delete_url_cache(url.short_code)
            logger.info("Expired URL: %s (evicted from cache)", url.short_code)


async def start_worker():
    setup_logging()
    from src.shared.core.tracing import init_metrics, init_tracing
    init_tracing()
    init_metrics()
    logger = get_logger("expiry-worker")
    logger.info("Expiry Worker started")
    interval = 30
    install_signal_handlers()

    while not await wait_for_shutdown():
        try:
            await scan_and_expire_urls(logger)
        except Exception as e:
            logger.warning("Error in expiry loop: %s", str(e))
        try:
            await asyncio.wait_for(asyncio.shield(wait_for_shutdown()), timeout=interval)
        except asyncio.TimeoutError:
            pass

    logger.info("Expiry Worker stopped")


if __name__ == "__main__":
    asyncio.run(start_worker())
