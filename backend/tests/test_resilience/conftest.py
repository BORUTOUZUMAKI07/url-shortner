from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Patch redis_client globally before any module imports it,
# otherwise the health endpoint (which calls redis_client.ping()) will fail.
import src.core.redis
_mock_redis = AsyncMock()
_mock_redis.ping.return_value = True
_mock_redis.get.return_value = None
_mock_redis.setex.return_value = True
_mock_redis.delete.return_value = True
_mock_redis.incr.return_value = 1
_mock_redis.expire.return_value = True
_mock_redis.eval.return_value = 0
src.core.redis.redis_client = _mock_redis

from src.main import create_app

pytestmark = pytest.mark.integration

_test_engine = None


def _get_test_engine():
    global _test_engine
    if _test_engine is None:
        from src.core.config import settings
        _test_engine = create_async_engine(
            settings.ASYNC_DATABASE_URI,
            echo=False,
            poolclass=NullPool,
        )
    return _test_engine


@asynccontextmanager
async def _test_lifespan(app):
    yield


@pytest_asyncio.fixture(autouse=True)
async def patch_async_session_local():
    import src.core.database as db_mod
    original = db_mod.AsyncSessionLocal
    test_session = async_sessionmaker(
        bind=_get_test_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )
    db_mod.AsyncSessionLocal = test_session
    try:
        yield
    finally:
        db_mod.AsyncSessionLocal = original


@pytest_asyncio.fixture(scope="session")
def app():
    return create_app(lifespan_override=_test_lifespan)
