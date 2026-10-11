"""Aggregation rollup: the one-at-a-time claim under concurrency.

The rollup ADDS to totals (upsert_rollup), so two workers that read the same
watermark would both apply the same Mongo window and permanently double-count.
The claim (setnx — the webhook consumer's trick) lets exactly one worker run a
cycle; a loser skips, and next cycle re-reads the winner's committed watermark
from Postgres, never a process-local value that could predate it.

These tests run in the no-Docker core suite: every external dependency is
patched, so nothing touches Postgres, Mongo, or Redis.
"""

import logging
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.analytics.workers import aggregation_worker as aw

logger = logging.getLogger("test-aggregation-claim")


@pytest.fixture(autouse=True)
def _reset_cursor():
    aw._last_cutoff = None
    yield
    aw._last_cutoff = None


class _FakeSession:
    def __init__(self):
        self.commit = AsyncMock()
        self.rollback = AsyncMock()


class _FakeSessionCM:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


def _rollup_env(mongo_rows=None, watermark=None, set_watermark_raises=False):
    """Patch the Mongo aggregate + repos + redis so the body runs with zero I/O.

    Returns (list-of-patches, deps) where deps holds the mocks the test needs
    to assert against (session, repos, redis).
    """
    if mongo_rows is None:
        mongo_rows = [{
            "_id": "hot",
            "short_code": "hot",
            "total_clicks": 3,
            "unique_clicks": 2,
            "max_clicked_at": datetime.now(timezone.utc),
        }]

    session = _FakeSession()
    url_repo = Mock()
    url_repo.get_url_ids_by_short_codes = AsyncMock(return_value={"hot": 1})
    analytics_repo = Mock()
    analytics_repo.upsert_rollup = AsyncMock()
    analytics_repo.set_watermark = AsyncMock(
        side_effect=RuntimeError("boom") if set_watermark_raises else None
    )
    analytics_repo.get_watermark = AsyncMock(return_value=watermark)

    click_event = Mock()
    click_event.aggregate.return_value.to_list = AsyncMock(return_value=mongo_rows)

    redis = Mock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    redis.delete = AsyncMock()

    patches = [
        patch.object(aw, "AsyncSessionLocal", lambda s=session: _FakeSessionCM(s)),
        patch.object(aw, "ClickEvent", click_event),
        patch.object(aw, "URLRepository", lambda db: url_repo),
        patch.object(aw, "AnalyticsRepository", lambda db: analytics_repo),
        patch.object(aw, "redis_client", redis),
    ]
    deps = {
        "session": session,
        "url_repo": url_repo,
        "analytics_repo": analytics_repo,
        "redis": redis,
    }
    return patches, deps


class TestRollupClaim:
    @pytest.mark.asyncio
    async def test_claim_held_skips_cycle_without_reading_cursor(self):
        load_cutoff = AsyncMock()
        with (
            patch.object(aw, "_try_claim", AsyncMock(return_value=False)),
            patch.object(aw, "_load_cutoff", load_cutoff),
            patch.object(aw, "ClickEvent") as click,
        ):
            await aw.run_aggregation_rollup(logger)

        # A loser must not even start reading the watermark or aggregating.
        load_cutoff.assert_not_awaited()
        click.aggregate.assert_not_called()

    @pytest.mark.asyncio
    async def test_success_rolls_up_commits_and_releases_claim(self):
        patches, deps = _rollup_env()
        with (
            patch.object(aw, "_try_claim", AsyncMock(return_value=True)),
            patch.object(aw, "_release_claim", AsyncMock()) as release,
        ):
            with ExitStack() as stack:
                for p in patches:
                    stack.enter_context(p)
                await aw.run_aggregation_rollup(logger)

        deps["url_repo"].get_url_ids_by_short_codes.assert_awaited_once()
        deps["analytics_repo"].upsert_rollup.assert_awaited_once()
        deps["analytics_repo"].set_watermark.assert_awaited_once()
        deps["session"].commit.assert_awaited_once()
        # Redis cursor cache refreshed after the commit.
        deps["redis"].setex.assert_awaited_once()
        release.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_error_releases_claim_and_commits_nothing(self):
        patches, deps = _rollup_env(set_watermark_raises=True)
        with (
            patch.object(aw, "_try_claim", AsyncMock(return_value=True)),
            patch.object(aw, "_release_claim", AsyncMock()) as release,
        ):
            with ExitStack() as stack:
                for p in patches:
                    stack.enter_context(p)
                with pytest.raises(RuntimeError):
                    await aw.run_aggregation_rollup(logger)

        # The failed window was never committed — the next cycle re-does it from
        # the still-old watermark, so nothing is lost and nothing double-counts.
        deps["session"].commit.assert_not_awaited()
        release.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_window_advances_redis_cursor_only(self):
        patches, deps = _rollup_env(mongo_rows=[])
        with patch.object(aw, "_try_claim", AsyncMock(return_value=True)):
            with ExitStack() as stack:
                for p in patches:
                    stack.enter_context(p)
                await aw.run_aggregation_rollup(logger)

        deps["analytics_repo"].set_watermark.assert_not_awaited()
        deps["session"].commit.assert_not_awaited()
        deps["redis"].setex.assert_awaited_once()


class TestClaimPrimitive:
    @pytest.mark.asyncio
    async def test_try_claim_delegates_to_setnx_with_ttl(self):
        redis = Mock()
        redis.setnx = AsyncMock(return_value=True)
        with patch.object(aw, "redis_client", redis):
            assert await aw._try_claim() is True
        redis.setnx.assert_awaited_once_with(aw._CLAIM_KEY, aw._CLAIM_TTL_SECONDS, "1")

    @pytest.mark.asyncio
    async def test_try_claim_returns_false_when_another_instance_holds_it(self):
        redis = Mock()
        redis.setnx = AsyncMock(return_value=False)
        with patch.object(aw, "redis_client", redis):
            assert await aw._try_claim() is False

    @pytest.mark.asyncio
    async def test_try_claim_fails_open_on_redis_error(self):
        redis = Mock()
        redis.setnx = AsyncMock(side_effect=RuntimeError("upstash down"))
        with patch.object(aw, "redis_client", redis):
            # A Redis outage must not stall analytics.
            assert await aw._try_claim() is True

    @pytest.mark.asyncio
    async def test_release_claim_deletes_key(self):
        redis = Mock()
        redis.delete = AsyncMock()
        with patch.object(aw, "redis_client", redis):
            await aw._release_claim()
        redis.delete.assert_awaited_once_with(aw._CLAIM_KEY)

    @pytest.mark.asyncio
    async def test_release_claim_swallows_redis_error(self):
        redis = Mock()
        redis.delete = AsyncMock(side_effect=RuntimeError("upstash down"))
        with patch.object(aw, "redis_client", redis):
            await aw._release_claim()  # must not raise


class TestAuthoritativeWatermark:
    @pytest.mark.asyncio
    async def test_load_cutoff_reads_postgres_every_cycle_not_memoized(self):
        session = _FakeSession()
        repo = Mock()
        newer = datetime.now(timezone.utc)
        repo.get_watermark = AsyncMock(return_value=newer)
        # A stale in-memory cursor must NOT win over Postgres: after a skipped
        # cycle the winner's committed watermark is the only correct resume point.
        aw._last_cutoff = newer - timedelta(hours=1)
        with (
            patch.object(aw, "AsyncSessionLocal", lambda s=session: _FakeSessionCM(s)),
            patch.object(aw, "AnalyticsRepository", lambda db: repo),
        ):
            cutoff = await aw._load_cutoff()

        assert cutoff == newer
        assert aw._last_cutoff == newer

    @pytest.mark.asyncio
    async def test_load_cutoff_falls_back_to_memory_when_postgres_down(self):
        session = _FakeSession()
        repo = Mock()
        repo.get_watermark = AsyncMock(side_effect=RuntimeError("db down"))
        aw._last_cutoff = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with (
            patch.object(aw, "AsyncSessionLocal", lambda s=session: _FakeSessionCM(s)),
            patch.object(aw, "AnalyticsRepository", lambda db: repo),
        ):
            cutoff = await aw._load_cutoff()

        assert cutoff == aw._last_cutoff
