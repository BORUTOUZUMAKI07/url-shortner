"""Rate-limit result parsing, 429 headers, fallback limiter, middleware wiring.

Covers the token-bucket state that now flows out of ``check_rate_limit`` (both
the Lua path and the in-process fallback) and the ``Retry-After`` +
``RateLimit-*`` headers every 429 must carry so well-behaved clients back off.
"""

from unittest.mock import AsyncMock, patch

import pytest
from starlette.requests import Request

from src.shared.core.config import settings
from src.shared.core.redis import (
    RateLimitResult,
    check_rate_limit,
    rate_limit_headers,
)


class TestRateLimitHeadersHelper:
    def test_allowed_request_has_no_retry_after(self):
        result = RateLimitResult(limited=False, remaining=7, reset_after_seconds=30.0)
        assert rate_limit_headers(result, 10) == {
            "RateLimit-Limit": "10",
            "RateLimit-Remaining": "7",
            "RateLimit-Reset": "30",
        }

    def test_limited_request_carries_retry_after_ceiled(self):
        result = RateLimitResult(
            limited=True, remaining=0,
            retry_after_seconds=99.2, reset_after_seconds=100.0,
        )
        headers = rate_limit_headers(result, 10)
        assert headers["Retry-After"] == "100"  # int(99.2) + 1 = ceil
        assert headers["RateLimit-Limit"] == "10"
        assert headers["RateLimit-Remaining"] == "0"
        assert headers["RateLimit-Reset"] == "100"

    def test_sub_second_retry_never_advertises_zero(self):
        result = RateLimitResult(limited=True, remaining=0, retry_after_seconds=0.05, reset_after_seconds=10.0)
        assert rate_limit_headers(result, 10)["Retry-After"] == "1"


class TestCheckRateLimitParsing:
    @pytest.mark.asyncio
    async def test_parses_lua_allowed(self):
        redis = AsyncMock()
        redis.eval = AsyncMock(return_value=[1, 9.5, 12345.0])
        with patch("src.shared.core.redis.redis_client", redis):
            result = await check_rate_limit("k", 10, 0.5)
        assert not result.limited
        assert result.remaining == 9
        assert result.retry_after_seconds is None
        assert result.reset_after_seconds == pytest.approx(1.0)  # (10 - 9.5) / 0.5

    @pytest.mark.asyncio
    async def test_parses_lua_limited_with_string_numbers(self):
        # Redis serializes a Lua number with a fractional part as a bulk string
        # ("0.4") and an integral one as an integer — parse both shapes.
        redis = AsyncMock()
        redis.eval = AsyncMock(return_value=[0, "0.4", "12345.0"])
        with patch("src.shared.core.redis.redis_client", redis):
            result = await check_rate_limit("k", 10, 0.5)
        assert result.limited
        assert result.remaining == 0
        assert result.retry_after_seconds == pytest.approx(1.2)  # (1 - 0.4) / 0.5
        assert result.reset_after_seconds == pytest.approx(19.2)  # (10 - 0.4) / 0.5

    @pytest.mark.asyncio
    async def test_falls_back_to_in_process_when_redis_fails(self):
        redis = AsyncMock()
        redis.eval = AsyncMock(side_effect=RuntimeError("upstash down"))
        with patch("src.shared.core.redis.redis_client", redis):
            with patch("src.shared.core.redis._limiter.token_bucket") as fallback:
                fallback.return_value = RateLimitResult(
                    limited=True, remaining=0, retry_after_seconds=3.0, reset_after_seconds=10.0
                )
                result = await check_rate_limit("k", 10, 0.5)
        assert result.limited
        assert result.retry_after_seconds == 3.0
        fallback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_in_process_limiter_refills_and_reports_state(self):
        from src.shared.core.redis import _limiter

        first = await _limiter.token_bucket("test:state:key", 2.0, 0.5)
        assert not first.limited
        assert first.remaining == 1

        second = await _limiter.token_bucket("test:state:key", 2.0, 0.5)
        assert not second.limited
        assert second.remaining == 0

        third = await _limiter.token_bucket("test:state:key", 2.0, 0.5)
        assert third.limited
        # Microseconds of wall-clock refill between calls make this a hair
        # under 2.0; abs tolerance absorbs the clock noise.
        assert third.retry_after_seconds == pytest.approx(2.0, abs=0.05)  # 1 token at 0.5/s


def _make_request(path: str = "/api/v1/urls") -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("203.0.113.7", 54321),
        "server": ("testserver", 80),
    }
    return Request(scope)


class TestRateLimitMiddlewareHeaders:
    @pytest.mark.asyncio
    async def test_429_response_carries_retry_after_headers(self):
        from src.shared.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(None)
        result = RateLimitResult(limited=True, remaining=0, retry_after_seconds=12.0, reset_after_seconds=60.0)

        async def fail_next(request):
            raise AssertionError("call_next must not run when limited")

        with patch("src.shared.middleware.rate_limit.check_rate_limit", AsyncMock(return_value=result)):
            response = await middleware.dispatch(_make_request(), fail_next)

        assert response.status_code == 429
        assert response.headers["Retry-After"] == "13"
        assert response.headers["RateLimit-Limit"] == str(settings.RATE_LIMIT_IP_CAPACITY)
        assert response.headers["RateLimit-Remaining"] == "0"
        assert "RateLimit-Reset" in response.headers

    @pytest.mark.asyncio
    async def test_allowed_request_passes_through(self):
        from starlette.responses import JSONResponse

        from src.shared.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(None)
        result = RateLimitResult(limited=False, remaining=9, reset_after_seconds=0.0)

        async def call_next(request):
            return JSONResponse({"ok": True})

        with patch("src.shared.middleware.rate_limit.check_rate_limit", AsyncMock(return_value=result)):
            response = await middleware.dispatch(_make_request(), call_next)

        assert response.status_code == 200
