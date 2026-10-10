"""L1 in-process URL cache: hit/miss, TTL, eviction, and invalidation wiring.

The L1 cache sits in front of Redis inside the shared ``get_url_cache`` /
``set_url_cache`` / ``delete_url_cache`` choke points, so every read, write,
and invalidation path (redirect, single-URL update/delete, bulk ops) is
covered through the same four functions these tests exercise.
"""

import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from src.shared.core.redis import (
    _url_l1_cache,
    delete_url_cache,
    delete_url_caches,
    get_url_cache,
    set_url_cache,
)


@pytest.fixture(autouse=True)
def reset_l1():
    _url_l1_cache.clear()
    _url_l1_cache._clock = time.monotonic
    yield
    _url_l1_cache.clear()
    _url_l1_cache._clock = time.monotonic


class TestInProcessUrlCache:
    def test_get_miss_returns_none(self):
        assert _url_l1_cache.get("abc") is None

    def test_set_then_get(self):
        _url_l1_cache.set("abc", {"short_code": "abc"})
        assert _url_l1_cache.get("abc") == {"short_code": "abc"}

    def test_expiry(self):
        _url_l1_cache._clock = lambda: 1000.0
        _url_l1_cache.set("abc", {"short_code": "abc"})
        assert _url_l1_cache.get("abc") is not None
        # One second past the 10s TTL boundary.
        _url_l1_cache._clock = lambda: 1010.0001
        assert _url_l1_cache.get("abc") is None
        # Expired entry is pruned, not returned and not retained.
        assert _url_l1_cache.get("abc") is None

    def test_delete_and_delete_many(self):
        for code in ("a", "b", "c"):
            _url_l1_cache.set(code, {"short_code": code})
        _url_l1_cache.delete("a")
        assert _url_l1_cache.get("a") is None
        _url_l1_cache.delete_many(["b", "c"])
        assert _url_l1_cache.get("b") is None
        assert _url_l1_cache.get("c") is None

    def test_fifo_eviction_when_full(self):
        _url_l1_cache.max_entries = 2
        _url_l1_cache.set("a", {"x": 1})
        _url_l1_cache.set("b", {"x": 2})
        _url_l1_cache.set("c", {"x": 3})
        # Oldest-inserted key is evicted first.
        assert _url_l1_cache.get("a") is None
        assert _url_l1_cache.get("b") is not None
        assert _url_l1_cache.get("c") is not None


class TestUrlCacheFunctions:
    @pytest.mark.asyncio
    async def test_get_hits_l1_without_touching_redis(self):
        _url_l1_cache.set("abc", {"short_code": "abc"})
        with patch("src.shared.core.redis.redis_client") as redis:
            redis.get = AsyncMock(side_effect=AssertionError("L1 hit must not touch Redis"))
            data = await get_url_cache("abc")
        assert data == {"short_code": "abc"}

    @pytest.mark.asyncio
    async def test_get_miss_reads_redis_and_populates_l1(self):
        with patch("src.shared.core.redis.redis_client") as redis:
            redis.get = AsyncMock(return_value=json.dumps({"short_code": "abc"}))
            data = await get_url_cache("abc")
        assert data == {"short_code": "abc"}
        assert _url_l1_cache.get("abc") == {"short_code": "abc"}

    @pytest.mark.asyncio
    async def test_get_redis_failure_fails_open_and_caches_nothing(self):
        with patch("src.shared.core.redis.redis_client") as redis:
            redis.get = AsyncMock(side_effect=RuntimeError("upstash down"))
            assert await get_url_cache("abc") is None
        assert _url_l1_cache.get("abc") is None

    @pytest.mark.asyncio
    async def test_set_populates_l1(self):
        with patch("src.shared.core.redis.redis_client") as redis:
            redis.setex = AsyncMock()
            await set_url_cache("abc", {"short_code": "abc"})
        assert _url_l1_cache.get("abc") == {"short_code": "abc"}

    @pytest.mark.asyncio
    async def test_set_redis_failure_still_populates_l1(self):
        # The data came from the DB — keeping it in L1 survives a Redis write
        # blip (the next hit is served locally, the DB remains authoritative).
        with patch("src.shared.core.redis.redis_client") as redis:
            redis.setex = AsyncMock(side_effect=RuntimeError("upstash down"))
            await set_url_cache("abc", {"short_code": "abc"})
        assert _url_l1_cache.get("abc") == {"short_code": "abc"}

    @pytest.mark.asyncio
    async def test_delete_clears_l1_and_redis(self):
        _url_l1_cache.set("abc", {"short_code": "abc"})
        with patch("src.shared.core.redis.redis_client") as redis:
            redis.delete = AsyncMock()
            await delete_url_cache("abc")
        assert _url_l1_cache.get("abc") is None
        redis.delete.assert_awaited_once_with("url:abc")

    @pytest.mark.asyncio
    async def test_delete_many_clears_l1_batch_and_redis(self):
        for code in ("a", "b"):
            _url_l1_cache.set(code, {"short_code": code})
        with patch("src.shared.core.redis.redis_client") as redis:
            redis.delete_many = AsyncMock()
            await delete_url_caches(["a", "b"])
        assert _url_l1_cache.get("a") is None
        assert _url_l1_cache.get("b") is None
        redis.delete_many.assert_awaited_once_with("url:a", "url:b")

    @pytest.mark.asyncio
    async def test_delete_many_empty_is_a_noop(self):
        with patch("src.shared.core.redis.redis_client") as redis:
            redis.delete_many = AsyncMock()
            await delete_url_caches([])
        redis.delete_many.assert_not_awaited()
