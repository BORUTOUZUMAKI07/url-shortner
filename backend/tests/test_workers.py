import logging
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.analytics.models.analytics import URLAnalyticsSummary
from src.analytics.workers.aggregation_worker import run_aggregation_rollup, run_purge_soft_deleted
from src.analytics.workers.analytics_worker import process_event
from src.identity.models.user import User
from src.links.models.url import URL, URLStatus
from src.links.repositories.url_repository import URLRepository
from src.shared.core.click_event import ClickEvent
from src.shared.core.mongodb import init_mongodb
from src.webhooks.workers.webhook_retry_worker import backoff_delay
from src.workspaces.models.workspace import Workspace

logger = logging.getLogger(__name__)

_test_engine = None


def _get_test_engine():
    global _test_engine
    if _test_engine is None:
        from src.shared.core.config import settings
        _test_engine = create_async_engine(settings.ASYNC_DATABASE_URI, echo=False, poolclass=NullPool)
    return _test_engine


def _get_session_local():
    return async_sessionmaker(_get_test_engine(), class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def reset_pooled_engine():
    from src.shared.core.database import engine as _pooled_engine
    # The shared app engine accumulates asyncpg connections on per-test
    # function-scoped loops. Disposing them from a later test's loop makes
    # asyncpg log "Event loop is closed" / "attached to a different loop"
    # (benign — SQLAlchemy catches it) — suppress that known noise.
    pool_logger = logging.getLogger("sqlalchemy.pool")
    prev_level = pool_logger.level
    pool_logger.setLevel(logging.CRITICAL)
    try:
        await _pooled_engine.dispose()
    finally:
        pool_logger.setLevel(prev_level)


@pytest_asyncio.fixture(autouse=True)
async def cleanup_worker_tables():
    yield
    async with _get_session_local()() as db:
        await db.execute(text("DELETE FROM urls WHERE short_code = 'test123'"))
        await db.execute(text("DELETE FROM workspaces WHERE name = 'Test Workspace'"))
        await db.execute(text("DELETE FROM users WHERE email = 'test@example.com'"))
        await db.commit()
    try:
        await ClickEvent.get_motor_collection().delete_many({})
    except Exception:
        pass


@pytest_asyncio.fixture
async def setup_db():
    async with _get_session_local()() as db:
        user = User(email="test@example.com", password_hash="test_hash", is_verified=True)
        db.add(user)
        await db.flush()
        workspace = Workspace(name="Test Workspace", owner_id=user.id)
        db.add(workspace)
        await db.flush()
        url = URL(
            short_code="test123",
            original_url="https://example.com",
            user_id=user.id,
            workspace_id=workspace.id,
            status=URLStatus.active,
        )
        db.add(url)
        await db.commit()
        await db.refresh(url)
        return url, user, workspace


@pytest.mark.asyncio
async def test_analytics_worker_process_event(setup_db):
    url, user, workspace = setup_db
    await init_mongodb()
    await process_event({
        "event_id": "evt-001",
        "short_code": "test123",
        "original_url": "https://example.com",
        "workspace_id": workspace.id,
        "ip_address": "192.168.1.1",
        "user_agent": "Mozilla/5.0",
        "referer": "https://twitter.com",
        "clicked_at": datetime.now(timezone.utc).isoformat(),
    }, logger)
    click_event = await ClickEvent.find_one(ClickEvent.event_id == "evt-001")
    assert click_event is not None
    assert click_event.short_code == "test123"
    assert click_event.ip_address == "192.168.1.1"


@pytest.mark.asyncio
async def test_aggregation_worker_rollup(setup_db):
    url, user, workspace = setup_db
    await init_mongodb()
    for i in range(5):
        event = ClickEvent(
            event_id=f"evt-{i:03d}",
            short_code="test123",
            original_url="https://example.com",
            workspace_id=workspace.id,
            ip_address=f"192.168.1.{i}",
            user_agent="Mozilla/5.0",
            clicked_at=datetime.now(timezone.utc),
        )
        await event.insert()
    await run_aggregation_rollup(logger)
    async with _get_session_local()() as db:
        result = await db.execute(
            select(URLAnalyticsSummary).where(URLAnalyticsSummary.url_id == url.id)
        )
        summary = result.scalar_one_or_none()
        assert summary is not None
        assert summary.total_clicks == 5
        assert summary.unique_clicks == 5


@pytest.mark.asyncio
async def test_query_time_expiry_excludes_expired_urls(setup_db):
    """Expiry is now computed at query time via _IS_NOT_EXPIRED in url_repository.
    An expired URL must not appear in get_workspace_urls results."""
    url, user, workspace = setup_db
    url.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    async with _get_session_local()() as db:
        db.add(url)
        await db.commit()
    async with _get_session_local()() as db:
        url_repo = URLRepository(db)
        result = await url_repo.get_workspace_urls(workspace_id=workspace.id)
        # The expired URL must not be returned
        assert all(item.short_code != "test123" for item in result["items"])


@pytest.mark.asyncio
async def test_purge_soft_deleted_urls(setup_db):
    """run_purge_soft_deleted hard-deletes URLs older than the grace period."""
    url, user, workspace = setup_db
    # Make the URL old enough to purge (> 30 days)
    url.created_at = datetime.now(timezone.utc) - timedelta(days=31)
    url.status = URLStatus.deleted
    async with _get_session_local()() as db:
        db.add(url)
        await db.commit()
    await init_mongodb()
    # Import and patch the purge interval to 0 so it runs immediately
    import src.analytics.workers.aggregation_worker as agg
    agg._last_purge_ts = 0.0
    agg._PURGE_STALE_SECONDS = 0  # no grace period for this test
    await run_purge_soft_deleted(logger)
    agg._PURGE_STALE_SECONDS = 30 * 86400  # restore
    async with _get_session_local()() as db:
        result = await db.execute(select(URL).where(URL.short_code == "test123"))
        assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_multiple_workers_end_to_end(setup_db):
    url, user, workspace = setup_db
    await init_mongodb()
    for i in range(10):
        await process_event({
            "event_id": f"e2e-evt-{i:03d}",
            "short_code": "test123",
            "original_url": "https://example.com",
            "workspace_id": workspace.id,
            "ip_address": f"172.16.0.{i}",
            "user_agent": "Mozilla/5.0",
            "clicked_at": datetime.now(timezone.utc).isoformat(),
        }, logger)
    await run_aggregation_rollup(logger)
    async with _get_session_local()() as db:
        result = await db.execute(
            select(URLAnalyticsSummary).where(URLAnalyticsSummary.url_id == url.id)
        )
        summary = result.scalar_one_or_none()
        assert summary is not None
        assert summary.total_clicks == 10
        assert summary.unique_clicks == 10
    url.status = URLStatus.deleted
    url.created_at = datetime.now(timezone.utc) - timedelta(days=31)
    async with _get_session_local()() as db:
        db.add(url)
        await db.commit()
    import src.analytics.workers.aggregation_worker as agg
    agg._PURGE_STALE_SECONDS = 0
    await run_purge_soft_deleted(logger)
    agg._PURGE_STALE_SECONDS = 30 * 86400
    async with _get_session_local()() as db:
        result = await db.execute(select(URL).where(URL.short_code == "test123"))
        assert result.scalar_one_or_none() is None
    click_events = await ClickEvent.find(ClickEvent.short_code == "test123").to_list()
    assert len(click_events) == 0


@pytest.mark.asyncio
async def test_metadata_worker_extract_and_store(setup_db):
    url, user, workspace = setup_db
    from src.webhooks.workers.metadata_worker import extract_metadata
    meta = await extract_metadata("https://example.com", logger)
    assert meta["title"] == "Example Domain"
    assert meta["description"] is None
    assert meta["og_image"] is None


@pytest.mark.asyncio
async def test_webhook_retry_worker_scan(setup_db):
    url, user, workspace = setup_db
    from src.webhooks.workers.webhook_retry_worker import retry_failed_events
    await retry_failed_events(logger)


def test_webhook_retry_backoff():
    assert backoff_delay(1) == 30
    assert backoff_delay(2) == 60
    assert backoff_delay(3) == 120
    assert backoff_delay(8) == 3600


@pytest.mark.asyncio
async def test_analytics_worker_json_fallback(setup_db):
    url, user, workspace = setup_db
    await init_mongodb()
    await process_event({
        "event_id": "json-fallback-test",
        "short_code": "test123",
        "original_url": "https://example.com",
        "workspace_id": workspace.id,
        "ip_address": "10.0.0.1",
        "user_agent": "curl/8.0",
        "referer": "",
        "clicked_at": datetime.now(timezone.utc).isoformat(),
    }, logger)
    click_event = await ClickEvent.find_one(ClickEvent.event_id == "json-fallback-test")
    assert click_event is not None
    assert click_event.ip_address == "10.0.0.1"
