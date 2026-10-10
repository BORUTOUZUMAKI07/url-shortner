"""Request coalescing on the redirect cache-miss path.

A cache-bust on a popular code (delete, bulk-disable, one-time consume) leaves
every concurrent miss free to run its own DB SELECT — the stampede the L1 cache
shrinks but cannot fully remove. ``_fetch_url`` shares one in-flight DB fetch
across all waiters; these tests pin that behavior and its failure mode.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.links.services.redirect_service import RedirectService, _fetch_inflight
from src.shared.errors.url import URLNotFound


@pytest.fixture(autouse=True)
def clear_inflight():
    _fetch_inflight.clear()
    yield
    _fetch_inflight.clear()


def _url_obj(short_code: str):
    return SimpleNamespace(
        id=1,
        short_code=short_code,
        original_url="https://example.com",
        workspace_id=1,
        is_ab_test=False,
        is_one_time=False,
        ios_url=None,
        android_url=None,
        password_hash=None,
        status=SimpleNamespace(value="active"),
        expires_at=None,
    )


def _make_service(repo) -> RedirectService:
    return RedirectService(url_repo=repo, workspace_repo=AsyncMock(), events=AsyncMock())


class TestSingleflightFetch:
    @pytest.mark.asyncio
    async def test_concurrent_misses_share_one_db_fetch(self):
        repo = AsyncMock()
        calls = {"n": 0}

        async def slow_load(code):
            calls["n"] += 1
            await asyncio.sleep(0.05)
            return _url_obj(code)

        repo.get_by_short_code = AsyncMock(side_effect=slow_load)
        svc = _make_service(repo)

        with (
            patch("src.links.services.redirect_service.get_url_cache", AsyncMock(return_value=None)),
            patch("src.links.services.redirect_service.set_url_cache", AsyncMock()) as set_cache,
        ):
            results = await asyncio.gather(*[svc._fetch_url("hot") for _ in range(5)])

        assert calls["n"] == 1
        assert len(results) == 5
        assert all(r["short_code"] == "hot" for r in results)
        set_cache.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_not_found_propagates_to_all_waiters(self):
        repo = AsyncMock()

        async def missing(code):
            await asyncio.sleep(0.02)
            return None

        repo.get_by_short_code = AsyncMock(side_effect=missing)
        svc = _make_service(repo)

        with patch("src.links.services.redirect_service.get_url_cache", AsyncMock(return_value=None)):
            results = await asyncio.gather(
                *[svc._fetch_url("nope") for _ in range(3)], return_exceptions=True
            )

        assert all(isinstance(r, URLNotFound) for r in results)
        assert repo.get_by_short_code.await_count == 1

    @pytest.mark.asyncio
    async def test_cancelled_waiter_does_not_kill_shared_fetch(self):
        repo = AsyncMock()
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_load(code):
            started.set()
            await release.wait()
            return _url_obj(code)

        repo.get_by_short_code = AsyncMock(side_effect=slow_load)
        svc = _make_service(repo)

        with patch("src.links.services.redirect_service.get_url_cache", AsyncMock(return_value=None)):
            first = asyncio.create_task(svc._fetch_url("hot"))
            await started.wait()

            waiter = asyncio.create_task(svc._fetch_url("hot"))
            await asyncio.sleep(0.01)
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter

            release.set()
            result = await first

        assert result["short_code"] == "hot"
        assert repo.get_by_short_code.await_count == 1

    @pytest.mark.asyncio
    async def test_done_task_is_replaced_not_reused(self):
        repo = AsyncMock()
        calls = {"n": 0}

        async def quick_load(code):
            calls["n"] += 1
            return _url_obj(code)

        repo.get_by_short_code = AsyncMock(side_effect=quick_load)
        svc = _make_service(repo)

        with patch("src.links.services.redirect_service.get_url_cache", AsyncMock(return_value=None)):
            first = await svc._fetch_url("hot")
            second = await svc._fetch_url("hot")

        assert first["short_code"] == "hot"
        assert second["short_code"] == "hot"
        # A completed fetch is never reused: the next miss runs a fresh,
        # authoritative DB lookup (the cache may have been invalidated again).
        assert calls["n"] == 2
