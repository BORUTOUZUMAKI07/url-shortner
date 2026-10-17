import asyncio
import json
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis as AsyncRedis
from upstash_redis.asyncio import Redis as UpstashRedis

from src.shared import get_logger
from src.shared.core.config import settings
from src.shared.core.metrics import record_cache_operation

logger = get_logger(__name__)


class RedisAdapter:
    """Unified adapter for Upstash REST and plain Redis.

    Production uses Upstash (REST) when credentials are provided; local
    development and docker-compose use a plain Redis instance via REDIS_URL.
    """

    def __init__(self, client: Any):
        self._client = client
        self._is_upstash = isinstance(client, UpstashRedis)

    async def ping(self):
        return await self._client.ping()

    async def get(self, key: str):
        return await self._client.get(key)

    async def mget(self, *keys: str):
        """Read several keys in ONE round trip (pipelined over REST)."""
        if self._is_upstash:
            cmd = ["MGET"] + list(keys)
            return await self._client.execute(cmd)
        return await self._client.mget(*keys)

    async def setex(self, key: str, ttl: int, value: str):
        return await self._client.set(key, value, ex=ttl)

    async def setnx(self, key: str, ttl: int, value: str) -> bool:
        """Atomic claim: set only if the key is absent.

        Returns True when this caller won the claim, False when the key already
        existed. Use this for anything that must run exactly once (idempotency
        markers, single-consumer locks).

        A plain get() + setex() is two round trips with a window between them
        in which a second caller reads "absent" and both proceed. With NX the
        get and the set are one atomic decision — exactly one caller wins.
        """
        if self._is_upstash:
            result = await self._client.execute(["SET", key, value, "NX", "EX", str(ttl)])
            return result is not None
        result = await self._client.set(key, value, nx=True, ex=ttl)
        return bool(result)

    async def getdel(self, key: str):
        """Atomically read and delete in ONE round trip. Returns the value or None.

        Use this instead of get() + delete() for anything single-use: a separate
        delete leaves a window in which a second caller reads the same value
        before either delete lands, so the value is handed out twice.
        """
        return await self._client.getdel(key)

    async def delete(self, key: str):
        return await self._client.delete(key)

    async def delete_many(self, *keys: str):
        """Delete several keys in ONE round trip."""
        if self._is_upstash:
            cmd = ["DEL"] + list(keys)
            return await self._client.execute(cmd)
        return await self._client.delete(*keys)

    async def incr(self, key: str):
        return await self._client.incr(key)

    async def expire(self, key: str, ttl: int):
        return await self._client.expire(key, ttl)

    async def eval(self, script: str, numkeys: int, *args):
        if self._is_upstash:
            cmd = ["EVAL", script, str(numkeys)] + list(args)
            return await self._client.execute(cmd)
        return await self._client.eval(script, numkeys, *args)


def _build_redis_client() -> RedisAdapter:
    if settings.UPSTASH_REDIS_REST_URL and settings.UPSTASH_REDIS_REST_TOKEN:
        logger.info("Redis client: Upstash REST")
        return RedisAdapter(
            UpstashRedis(url=settings.UPSTASH_REDIS_REST_URL, token=settings.UPSTASH_REDIS_REST_TOKEN)
        )
    logger.info("Redis client: plain Redis at %s", settings.REDIS_URL)
    return RedisAdapter(AsyncRedis.from_url(settings.REDIS_URL, decode_responses=True))


redis_client: RedisAdapter = _build_redis_client()

_RETRY_DELAYS = [1, 2, 4, 8, 16]


async def init_redis():
    for attempt, delay in enumerate(_RETRY_DELAYS):
        try:
            await redis_client.ping()
            logger.info("Redis (Upstash REST) connected successfully.")
            return redis_client
        except Exception as e:
            logger.warning("Redis ping attempt %d failed: %s", attempt + 1, e)
            if attempt < len(_RETRY_DELAYS) - 1:
                await asyncio.sleep(delay)
            else:
                logger.error("Redis failed to connect after %d attempts", len(_RETRY_DELAYS))
                raise


TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local current_time = tonumber(ARGV[3])
local requested = tonumber(ARGV[4] or 1)

local bucket = redis.call('HMGET', key, 'tokens', 'last_updated')
local tokens = tonumber(bucket[1])
local last_updated = tonumber(bucket[2])

if not tokens then
    tokens = capacity
    last_updated = current_time
else
    local delta = math.max(0, current_time - last_updated)
    tokens = math.min(capacity, tokens + delta * refill_rate)
end

if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_updated', current_time)
    redis.call('EXPIRE', key, 86400)
    return {1, tokens, current_time}
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_updated', current_time)
    redis.call('EXPIRE', key, 86400)
    return {0, tokens, current_time}
end
"""


@dataclass
class RateLimitResult:
    """Outcome of a token-bucket check plus the state needed for 429 headers.

    ``remaining`` and ``reset_after_seconds`` describe the bucket *after* this
    request was counted; ``retry_after_seconds`` is how long the caller should
    wait before one token refills (None when the request was allowed).
    """

    limited: bool
    remaining: int
    retry_after_seconds: float | None = None
    reset_after_seconds: float = 0.0


def rate_limit_headers(result: RateLimitResult, limit: int) -> dict[str, str]:
    """Standard 429 headers: RFC 6585 ``Retry-After`` plus the IETF rate-limit
    draft trio (``RateLimit-Limit`` / ``RateLimit-Remaining`` / ``RateLimit-Reset``,
    reset expressed in delta-seconds). Every 429 the API emits should carry
    these so well-behaved clients back off instead of hammering a refilling
    bucket. ``RateLimit-Reset`` is capped at one bucket-full of refill time.
    """
    headers = {
        "RateLimit-Limit": str(limit),
        "RateLimit-Remaining": str(result.remaining),
        "RateLimit-Reset": str(int(result.reset_after_seconds)),
    }
    if result.limited and result.retry_after_seconds is not None:
        # ceil via int()+1: never advertise 0, and a fractional wait must round
        # *up* so the client does not retry a millisecond too early.
        headers["Retry-After"] = str(max(1, int(result.retry_after_seconds) + 1))
    return headers


async def check_rate_limit(key: str, capacity: int, refill_rate_per_sec: float) -> RateLimitResult:
    """Token-bucket check. Returns the bucket state so callers can emit
    Retry-After / RateLimit-* headers on a 429."""
    try:
        now = time.time()
        result = await redis_client.eval(
            TOKEN_BUCKET_LUA,
            1,
            key,
            str(capacity),
            str(refill_rate_per_sec),
            str(now),
            "1"
        )
        # Redis serializes a Lua number with a fractional part as a bulk string
        # ("9.87") and an integral one as an integer (9) — parse both shapes.
        allowed = int(result[0])
        tokens = float(result[1])
        if allowed:
            return RateLimitResult(
                limited=False,
                remaining=int(tokens),
                retry_after_seconds=None,
                reset_after_seconds=max(0.0, (float(capacity) - tokens) / refill_rate_per_sec),
            )
        return RateLimitResult(
            limited=True,
            remaining=int(tokens),
            retry_after_seconds=max(0.0, (1.0 - tokens) / refill_rate_per_sec),
            reset_after_seconds=max(0.0, (float(capacity) - tokens) / refill_rate_per_sec),
        )
    except Exception as e:
        logger.error("Rate limit check failed for key %s (falling back to in-process limiter): %s", key, e)
        return await _limiter.token_bucket(key, float(capacity), refill_rate_per_sec)


class _InProcessLimiter:
    """Process-local fallback used when Redis is unreachable.

    This is a per-instance approximation (N app instances get ~Nx capacity) but
    it keeps the service enforcing limits instead of silently failing open. The
    token bucket mirrors ``TOKEN_BUCKET_LUA`` and the quota counter mirrors the
    daily API-key quota. Stale entries are pruned on each call once the dicts
    grow large, so memory stays bounded.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._buckets: dict[str, list[float]] = {}          # key -> [tokens, last_updated]
        self._quotas: dict[str, tuple[int, str]] = {}       # key -> (used, day)
        self._last_prune = 0.0

    async def _prune(self, now: float) -> None:
        if now - self._last_prune < 60.0:
            return
        self._last_prune = now
        for bkey, bucket in list(self._buckets.items()):
            if now - bucket[1] > 3600.0:
                self._buckets.pop(bkey, None)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for qkey, quota_state in list(self._quotas.items()):
            if quota_state[1] != today:
                self._quotas.pop(qkey, None)

    async def token_bucket(self, key: str, capacity: float, refill_rate: float) -> RateLimitResult:
        """Return the bucket state (mirrors check_rate_limit's Lua path)."""
        async with self._lock:
            now = time.time()
            await self._prune(now)
            state = self._buckets.get(key)
            if state is None:
                tokens, last = float(capacity), now
            else:
                tokens, last = state
                tokens = min(capacity, tokens + (now - last) * refill_rate)
            if tokens >= 1.0:
                tokens -= 1.0
                self._buckets[key] = [tokens, now]
                return RateLimitResult(
                    limited=False,
                    remaining=int(tokens),
                    retry_after_seconds=None,
                    reset_after_seconds=max(0.0, (capacity - tokens) / refill_rate),
                )
            self._buckets[key] = [tokens, now]
            return RateLimitResult(
                limited=True,
                remaining=int(tokens),
                retry_after_seconds=max(0.0, (1.0 - tokens) / refill_rate),
                reset_after_seconds=max(0.0, (capacity - tokens) / refill_rate),
            )

    async def consume_quota(self, key: str, quota: int) -> bool:
        """Atomically consume one unit of a daily quota; False when exhausted."""
        async with self._lock:
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            cache_key = f"{key}:{day}"
            used, day_stamp = self._quotas.get(cache_key, (0, day))
            if day_stamp != day:
                used = 0
            if used >= quota:
                return False
            self._quotas[cache_key] = (used + 1, day)
            return True


_limiter = _InProcessLimiter()


async def in_process_consume_quota(key: str, quota: int) -> bool:
    return await _limiter.consume_quota(key, quota)


class _InProcessUrlCache:
    """L1 cache in front of Redis for redirect lookups.

    The redirect hot path otherwise pays one Upstash REST HTTPS round trip
    (~100-200ms) per hit just for the ``get_url_cache`` GET — even for codes
    cached hours ago. This tiny process-local cache serves the hottest codes
    without a network hop. Properties:

      - **Short TTL** (seconds, vs the 24h Redis TTL): N-instance staleness
        after a mutation is bounded and invisible — the downstream cache
        already accepts up to 24h of staleness.
      - **Bounded**: FIFO eviction past ``max_entries`` (dict preserves
        insertion order, so the oldest-inserted key is first).
      - **Lock-free**: CPython dict operations are atomic under the GIL; a
        concurrent set/evict racing a get can only cause a redundant re-fetch,
        never a torn read.
      - **Caches only successes** (never failures), preserving the fail-open
        semantics of ``get_url_cache``.
    """

    __slots__ = ("_data", "ttl_seconds", "max_entries", "_clock")

    def __init__(self, ttl_seconds: float = 10.0, max_entries: int = 8192):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._data: dict[str, tuple[float, dict]] = {}
        self._clock = time.monotonic

    def get(self, short_code: str) -> dict | None:
        entry = self._data.get(short_code)
        if entry is None:
            return None
        inserted_at, data = entry
        if self._clock() - inserted_at >= self.ttl_seconds:
            self._data.pop(short_code, None)
            return None
        return data

    def set(self, short_code: str, data: dict) -> None:
        if len(self._data) >= self.max_entries:
            try:
                self._data.pop(next(iter(self._data)))
            except StopIteration:
                pass
        self._data[short_code] = (self._clock(), data)

    def delete(self, short_code: str) -> None:
        self._data.pop(short_code, None)

    def delete_many(self, short_codes: Iterable[str]) -> None:
        for code in short_codes:
            self._data.pop(code, None)

    def clear(self) -> None:
        self._data.clear()


_url_l1_cache = _InProcessUrlCache()


async def get_url_cache(short_code: str) -> dict | None:
    started = time.perf_counter()
    hit = _url_l1_cache.get(short_code)
    if hit is not None:
        record_cache_operation("get", True, time.perf_counter() - started, layer="l1")
        return hit
    try:
        data = await redis_client.get(f"url:{short_code}")
        if data:
            parsed: dict = json.loads(data)
            _url_l1_cache.set(short_code, parsed)
            record_cache_operation("get", True, time.perf_counter() - started, layer="redis")
            return parsed
        record_cache_operation("get", False, time.perf_counter() - started, layer="redis")
        return None
    except Exception as e:
        logger.debug("Cache read failed for %s: %s", short_code, e)
        record_cache_operation("get", False, time.perf_counter() - started, layer="redis")
        return None


async def set_url_cache(short_code: str, url_data: dict, ttl: int = 86400) -> None:
    # Populate L1 with the freshly-fetched row so the next hit skips Redis.
    # The L1 entry is bounded by its own (much shorter) TTL regardless of ttl.
    _url_l1_cache.set(short_code, url_data)
    try:
        await redis_client.setex(f"url:{short_code}", ttl, json.dumps(url_data))
    except Exception as e:
        logger.warning("Cache write failed for %s: %s", short_code, e)


async def delete_url_cache(short_code: str) -> None:
    _url_l1_cache.delete(short_code)
    try:
        await redis_client.delete(f"url:{short_code}")
    except Exception as e:
        logger.debug("Cache delete failed for %s: %s", short_code, e)


async def delete_url_caches(short_codes: list[str]) -> None:
    """Evict a batch of URL cache entries in ONE round trip.

    The bulk endpoints used to call delete_url_cache() in a loop — one Upstash
    HTTPS request (~100-200ms) per URL in the batch, serial. A 50-URL bulk
    delete paid ~10s of pure round-trip latency on top of the DB work.
    """
    if not short_codes:
        return
    _url_l1_cache.delete_many(short_codes)
    try:
        await redis_client.delete_many(*(f"url:{code}" for code in short_codes))
    except Exception as e:
        logger.debug("Cache delete failed for %s: %s", short_codes, e)


async def check_redis_health() -> bool:
    try:
        await redis_client.ping()
        return True
    except Exception:
        return False
