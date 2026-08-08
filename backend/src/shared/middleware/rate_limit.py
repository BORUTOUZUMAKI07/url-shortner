import time

from fastapi import HTTPException, Request, status
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from src.identity.models.user import User
from src.shared.core.config import settings
from src.shared.core.database import AsyncSessionLocal
from src.shared.core.redis import check_rate_limit

# Short-lived in-process plan cache so premium upgrades take effect without a
# token refresh while avoiding a DB query on every request.
_user_plan_cache: dict[int, tuple[str, float]] = {}
_USER_PLAN_CACHE_TTL = 60  # seconds


async def _get_user_plan(user_id: int) -> str:
    now = time.time()
    cached = _user_plan_cache.get(user_id)
    if cached and cached[1] > now:
        return cached[0]
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        plan = user.plan if user else "free"
    _user_plan_cache[user_id] = (plan, now + _USER_PLAN_CACHE_TTL)
    return plan


def invalidate_user_plan_cache(user_id: int) -> None:
    _user_plan_cache.pop(user_id, None)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health", "/metrics", "/favicon.ico"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        ip_key = f"rl:ip:{client_ip}:{request.url.path}"
        limited = await check_rate_limit(ip_key, settings.RATE_LIMIT_IP_CAPACITY, settings.RATE_LIMIT_IP_REFILL)
        if limited:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded. Try again later.")

        user_id = None
        plan = "free"
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from jose import jwt as jose_jwt
                payload = jose_jwt.decode(auth_header[7:], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                user_id = payload.get("sub")
            except JWTError:
                pass

        if user_id:
            try:
                user_id_int = int(user_id)
            except (TypeError, ValueError):
                user_id_int = None
            if user_id_int is not None:
                plan = await _get_user_plan(user_id_int)
                if plan in ("premium", "enterprise"):
                    cap, refill = settings.RATE_LIMIT_USER_PREMIUM_CAPACITY, settings.RATE_LIMIT_USER_PREMIUM_REFILL
                else:
                    cap, refill = settings.RATE_LIMIT_USER_FREE_CAPACITY, settings.RATE_LIMIT_USER_FREE_REFILL
                user_key = f"rl:user:{user_id_int}"
                user_limited = await check_rate_limit(user_key, cap, refill)
                if user_limited:
                    raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded. Try again later.")

        request.state.user_id = int(user_id) if user_id else None
        request.state.plan = plan

        response = await call_next(request)
        return response
