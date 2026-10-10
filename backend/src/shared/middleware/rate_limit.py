from fastapi import Request, status
from fastapi.responses import JSONResponse
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.core.client_ip import get_client_ip
from src.shared.core.config import settings
from src.shared.core.redis import RateLimitResult, check_rate_limit, rate_limit_headers
from src.shared.core.user_plan import DatabaseUserPlanResolver, UserPlanResolver

# Default resolver used by the middleware unless a concrete one is injected.
# Kept as a single shared instance so invalidate_user_plan_cache() below hits
# the same cache the middleware reads.
_default_plan_resolver = DatabaseUserPlanResolver()


def invalidate_user_plan_cache(user_id: int) -> None:
    _default_plan_resolver.invalidate(user_id)


def _rate_limited_response(result: RateLimitResult, limit: int) -> JSONResponse:
    """429 response with Retry-After + RateLimit-* headers.

    Returned (not raised) from the middleware: a raise here would have to
    propagate through the middleware stack and into an exception handler that
    then rebuilds the response — headers set on the exception do not reliably
    survive that hop. Returning a Response keeps them intact.
    """
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Rate limit exceeded. Try again later.", "error_code": "RATE_LIMITED"},
        headers=rate_limit_headers(result, limit),
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, plan_resolver: UserPlanResolver | None = None):
        super().__init__(app)
        self._plan_resolver = plan_resolver or _default_plan_resolver

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health", "/metrics", "/favicon.ico"):
            return await call_next(request)

        # TRUST_PROXY-aware: behind Render, request.client.host is the proxy, so
        # keying on it collapsed every visitor into a single rate-limit bucket.
        client_ip = get_client_ip(request)
        ip_key = f"rl:ip:{client_ip}:{request.url.path}"
        ip_result = await check_rate_limit(ip_key, settings.RATE_LIMIT_IP_CAPACITY, settings.RATE_LIMIT_IP_REFILL)
        if ip_result.limited:
            return _rate_limited_response(ip_result, settings.RATE_LIMIT_IP_CAPACITY)

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
                user_result = await check_rate_limit(user_key, cap, refill)
                if user_result.limited:
                    return _rate_limited_response(user_result, cap)

        request.state.user_id = int(user_id) if user_id else None
        request.state.plan = plan

        response = await call_next(request)
        return response
