"""Per-account login backstop, alongside the per-IP auth budget.

The per-IP bucket is bypassable by a distributed attacker (one IP each), so the
account itself gets a second bucket. It is failure-weighted in practice because
the route deletes the key after a successful login; only failed attempts remain.
The key is a hash, so Redis never stores the address.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from src.identity.routes import auth as auth_routes
from src.shared.core.redis import RateLimitResult


class TestLoginAccountKey:
    def test_key_is_a_hash_and_normalizes_email(self):
        a = auth_routes._login_account_key("  Foo@Example.com ")
        b = auth_routes._login_account_key("foo@example.com")
        assert a == b
        assert "foo@example.com" not in a
        assert a.startswith("rl:login_account:")


class TestEnforceLoginAccountLimit:
    async def test_allowed_returns_the_key(self):
        allowed = RateLimitResult(limited=False, remaining=49, reset_after_seconds=1.0)
        with patch.object(auth_routes, "check_rate_limit", AsyncMock(return_value=allowed)) as check:
            key = await auth_routes._enforce_login_account_limit(None, "foo@example.com")

        assert key == auth_routes._login_account_key("foo@example.com")
        check.assert_awaited_once()
        args, kwargs = check.await_args
        assert args[0] == key
        assert kwargs["capacity"] == auth_routes._LOGIN_ACCOUNT_CAPACITY

    async def test_limited_raises_429_with_retry_headers(self):
        limited = RateLimitResult(
            limited=True,
            remaining=0,
            retry_after_seconds=12.2,
            reset_after_seconds=60.0,
        )
        with patch.object(auth_routes, "check_rate_limit", AsyncMock(return_value=limited)):
            with pytest.raises(HTTPException) as exc:
                await auth_routes._enforce_login_account_limit(None, "foo@example.com")

        assert exc.value.status_code == 429
        assert exc.value.headers["Retry-After"] == "13"
        assert exc.value.headers["RateLimit-Limit"] == str(auth_routes._LOGIN_ACCOUNT_CAPACITY)


class TestClearLoginAccountLimit:
    async def test_clear_is_best_effort(self):
        with patch.object(auth_routes.redis_client, "delete", AsyncMock(side_effect=RuntimeError("down"))):
            await auth_routes._clear_login_account_limit("rl:login_account:x")

    async def test_clear_deletes_the_key(self):
        delete = AsyncMock()
        with patch.object(auth_routes.redis_client, "delete", delete):
            await auth_routes._clear_login_account_limit("rl:login_account:x")
        delete.assert_awaited_once_with("rl:login_account:x")
