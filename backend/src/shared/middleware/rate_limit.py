from fastapi import HTTPException, Request, status
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.core.config import settings
from src.shared.core.redis import check_rate_limit
from src.shared.core.user_plan import DatabaseUserPlanResolver, UserPlanResolver

# Default resolver used by the middleware unless a concrete one is injected.
# Kept as a single shared instance so invalidate_user_plan_cache() below hits
# the same cache the middleware reads.
_default_plan_resolver = DatabaseUserPlanResolver()


def invalidate_user_plan_cache(user_id: int) -> None:
    _default_plan_resolver.invalidate(user_id)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, plan_resolver: UserPlanResolver | None = None):
        super().__init__(app)
        self._plan_resolver = plan_resolver or _default_plan_resolver

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
                plan = await self._plan_resolver.resolve(user_id_int)
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
