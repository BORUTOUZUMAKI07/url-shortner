"""
API Key authentication and quota enforcement middleware.
"""

from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy import select

from src.identity.models.api_key import APIKey, APIKeyStatus
from src.identity.models.user import User
from src.shared import get_logger
from src.shared.core.database import AsyncSessionLocal
from src.shared.core.redis import in_process_consume_quota, redis_client
from src.shared.core.security import verify_password
from src.shared.errors import ForbiddenError, RateLimitError, UnauthorizedError

logger = get_logger(__name__)


class APIKeyQuotaManager:
    """Manages API key quota tracking and enforcement."""

    QUOTA_FREE = 1_000  # 1,000 requests/day for free tier
    QUOTA_PREMIUM = 100_000  # 100,000 requests/day for premium tier

    # Atomic check-and-increment: returns 1 and increments when the quota is
    # available, otherwise 0 without incrementing. Eliminates the race between
    # the previous GET-then-INCR that could overrun the daily cap.
    CHECK_AND_INCREMENT_LUA = """
local key = KEYS[1]
local quota = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local current = tonumber(redis.call('GET', key) or '0')
if current >= quota then
    return 0
end
redis.call('INCR', key)
redis.call('EXPIRE', key, ttl)
return 1
"""

    @staticmethod
    def get_quota_for_user(user_plan: str) -> int:
        """Get daily quota based on user's plan."""
        if user_plan in ("premium", "enterprise"):
            return APIKeyQuotaManager.QUOTA_PREMIUM
        return APIKeyQuotaManager.QUOTA_FREE

    @staticmethod
    async def get_remaining_quota(api_key_id: int, user_plan: str) -> int:
        """Get remaining quota for today."""
        quota = APIKeyQuotaManager.get_quota_for_user(user_plan)
        redis_key = f"api_key_quota:{api_key_id}:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

        current_usage = await redis_client.get(redis_key)
        current_usage = int(current_usage) if current_usage else 0

        return max(0, quota - current_usage)


async def authenticate_api_key(request: Request) -> tuple[User, APIKey]:
    """
    Authenticate API key from Authorization header.
    Returns: (User, APIKey) tuple
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise UnauthorizedError("Missing API key in Authorization header")

    if not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Invalid Authorization header format. Expected 'Bearer <api_key>'")

    raw_key = auth_header.split(" ")[1]

    async with AsyncSessionLocal() as db:
        # Find API key by prefix (to reduce lookup time)
        prefix = raw_key[:8]
        result = await db.execute(
            select(APIKey, User).join(User).where(APIKey.prefix == prefix)
        )
        row = result.one_or_none()

        if not row:
            raise UnauthorizedError("Invalid API key")

        api_key, user = row

        if api_key.status != APIKeyStatus.active:
            raise ForbiddenError("API key has been revoked")

        if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
            raise ForbiddenError("API key has expired")

        if not verify_password(raw_key, api_key.key_hash):
            raise UnauthorizedError("Invalid API key")

        # Update last_used_at
        api_key.last_used_at = datetime.now(timezone.utc)
        await db.commit()

        return user, api_key


async def verify_api_key_quota(api_key_id: int, user_plan: str) -> None:
    """
    Verify that API key has remaining quota, atomically consuming one request.
    Raises RateLimitError when the daily quota is exhausted.
    Falls back to a process-local counter when Redis is unreachable.
    """
    quota = APIKeyQuotaManager.get_quota_for_user(user_plan)
    redis_key = f"api_key_quota:{api_key_id}:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    try:
        allowed = await redis_client.eval(
            APIKeyQuotaManager.CHECK_AND_INCREMENT_LUA,
            1,
            redis_key,
            str(quota),
            "86400",
        )
    except Exception as e:
        logger.error("API key quota check failed for key %d (falling back to in-process counter): %s", api_key_id, e)
        allowed = await in_process_consume_quota(f"api_key_quota:{api_key_id}", quota)
    if allowed != 1:
        try:
            remaining = await APIKeyQuotaManager.get_remaining_quota(api_key_id, user_plan)
        except Exception:
            remaining = 0
        raise RateLimitError(f"API key quota exceeded. Limit: {quota} requests/day. Remaining: {remaining}")
