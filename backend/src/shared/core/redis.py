import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis as AsyncRedis
from upstash_redis.asyncio import Redis as UpstashRedis

from src.shared import get_logger
from src.shared.core.config import settings

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
    return 1
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_updated', current_time)
    redis.call('EXPIRE', key, 86400)
    return 0
end
"""


async def check_rate_limit(key: str, capacity: int, refill_rate_per_sec: float) -> bool:
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
        return result == 0  # type: ignore[no-any-return]
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

    async def token_bucket(self, key: str, capacity: float, refill_rate: float) -> bool:
        """Return True when the request is limited (mirrors check_rate_limit)."""
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
                return False
            self._buckets[key] = [tokens, now]
            return True

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


async def get_url_cache(short_code: str) -> dict | None:
    try:
        data = await redis_client.get(f"url:{short_code}")
        if data:
            return json.loads(data)  # type: ignore[no-any-return]
        return None
    except Exception as e:
        logger.debug("Cache read failed for %s: %s", short_code, e)
        return None


async def set_url_cache(short_code: str, url_data: dict, ttl: int = 86400) -> None:
    try:
        await redis_client.setex(f"url:{short_code}", ttl, json.dumps(url_data))
    except Exception as e:
        logger.warning("Cache write failed for %s: %s", short_code, e)


async def delete_url_cache(short_code: str) -> None:
    try:
        await redis_client.delete(f"url:{short_code}")
    except Exception as e:
        logger.debug("Cache delete failed for %s: %s", short_code, e)


async def check_redis_health() -> bool:
    try:
        await redis_client.ping()
        return True
    except Exception:
        return False
