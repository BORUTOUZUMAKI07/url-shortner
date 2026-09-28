"""RedisAdapter.setnx and batched URL-cache eviction.

setnx is the atomic claim primitive the webhook idempotency rework depends on:
a plain get() + setex() is two round trips with a window in which two callers
both read "absent" and both proceed. NX makes the get and the set one decision
— exactly one caller wins.
"""
from unittest.mock import patch

from src.shared.core.redis import RedisAdapter, delete_url_caches


class UpstashDouble:
    """Models Upstash's `SET key value NX EX ttl`: "OK" when set, None on a clash."""

    def __init__(self):
        self.store = {}
        self.commands = []

    async def execute(self, cmd):
        self.commands.append(cmd)
        key, value = cmd[1], cmd[2]
        if key in self.store:
            return None
        self.store[key] = value
        return "OK"


class PlainDouble:
    """Models redis-py's set(key, value, nx=True, ex=ttl): True / None."""

    def __init__(self):
        self.store = {}
        self.calls = []

    async def set(self, key, value, nx=False, ex=None):
        self.calls.append((key, value, nx, ex))
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True


async def test_setnx_upstash_claims_once_atomically():
    client = UpstashDouble()
    adapter = RedisAdapter(client)
    adapter._is_upstash = True

    assert await adapter.setnx("k", 90, "1") is True
    assert await adapter.setnx("k", 90, "1") is False
    assert client.commands == [
        ["SET", "k", "1", "NX", "EX", "90"],
        ["SET", "k", "1", "NX", "EX", "90"],
    ]


async def test_setnx_plain_redis_uses_nx_ex():
    client = PlainDouble()
    adapter = RedisAdapter(client)

    assert await adapter.setnx("k", 60, "lock") is True
    assert await adapter.setnx("k", 60, "lock") is False
    assert client.calls == [("k", "lock", True, 60), ("k", "lock", True, 60)]


async def test_delete_url_caches_evicts_batch_in_one_round_trip():
    class Recording:
        def __init__(self):
            self.batches = []

        async def delete_many(self, *keys):
            self.batches.append(keys)

    redis = Recording()
    with patch("src.shared.core.redis.redis_client", redis):
        await delete_url_caches(["abc123", "def456", "ghi789"])
    assert redis.batches == [("url:abc123", "url:def456", "url:ghi789")]


async def test_delete_url_caches_empty_is_a_noop():
    with patch("src.shared.core.redis.redis_client") as redis:
        await delete_url_caches([])
    redis.delete_many.assert_not_called()


async def test_delete_url_caches_survives_redis_failure():
    class Failing:
        async def delete_many(self, *keys):
            raise ConnectionError("upstream unavailable")

    with patch("src.shared.core.redis.redis_client", Failing()):
        # Eviction is best-effort: a stale cache entry is refreshed by the next
        # hit, but a redirect that fails because Redis threw would be far worse.
        await delete_url_caches(["abc123"])
