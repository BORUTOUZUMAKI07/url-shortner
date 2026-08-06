import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.shared.core.config import settings

logger = logging.getLogger(__name__)

_RETRY_DELAYS = [1, 2, 4, 8, 16]

engine = create_async_engine(
    settings.ASYNC_DATABASE_URI,
    echo=False,
    pool_size=20,
    max_overflow=10,
    connect_args={"statement_cache_size": 0},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db():
    """Verify database connectivity at startup with exponential backoff.

    Called during the app lifespan.  If all attempts fail the application
    continues to serve requests in degraded mode – individual endpoints
    that hit the database will return 5xx errors.
    """
    for attempt, delay in enumerate(_RETRY_DELAYS):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection verified successfully.")
            return
        except Exception as e:
            logger.warning("Database connection attempt %d failed: %s", attempt + 1, e)
            if attempt < len(_RETRY_DELAYS) - 1:
                await asyncio.sleep(delay)
    logger.error("Database unreachable after %d attempts — serving in degraded mode", len(_RETRY_DELAYS))


async def check_db_health() -> bool:
    """Returns ``True`` if the database is reachable."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
