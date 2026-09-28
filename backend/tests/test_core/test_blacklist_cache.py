"""A logged-out access token must not become valid again.

The finding: `deps.get_current_user` cached "this token is revoked" for 60
seconds in a process-local dict, but the Redis blacklist entry it was a cache
*of* lives until the token's own `exp` — up to ACCESS_TOKEN_EXPIRE_MINUTES
(60) later.

    cached = _blacklist_cache.get(token)
    if cached is not None and cached > now:
        raise TokenRevoked()
    if cached is None:                       # <-- only None consulted Redis
        ...

The `cached is None` guard is the bug. An entry that was present but whose 60s
TTL had passed satisfies neither branch, so execution fell straight through to
`decode_token(token)` and the request was authorized. The window opened 60
seconds after every logout and stayed open until the token expired on its own —
so a stolen access token kept working for the rest of its hour, and each use
refreshed nothing and blocked nothing.

Worse for the "cache" framing: nothing ever removed the entry. `_blacklist_cache`
gained one key per revoked token for the life of the process, forever.

Both are fixed by treating a stale entry as the miss it is — which is also what
the comment above the dict has always claimed ("a token that is NOT in the cache
is never treated as revoked... the first check after blacklisting hits Redis").

These call the real dependency with a fake Redis, so no DB or container is
needed. The cache dict is cleared between tests because it is module state.
"""

import time
from datetime import timedelta
from unittest.mock import patch

import pytest

from src.identity.models.user import User
from src.shared.core import deps
from src.shared.core.security import create_access_token
from src.shared.errors import TokenRevoked


class _FakeRedis:
    """Answers the blacklist key from its own store, like the real thing."""

    def __init__(self):
        self.data: dict[str, str] = {}
        self.gets: list[str] = []

    async def get(self, key):
        self.gets.append(key)
        return self.data.get(key)


def _creds(token: str):
    class _C:
        credentials = token

    return _C()


def _user() -> User:
    return User(id=1, email="a@example.com", is_active=True, password_hash="x")


@pytest.fixture(autouse=True)
def _clear_cache():
    deps._blacklist_cache.clear()
    yield
    deps._blacklist_cache.clear()


async def _call(token: str, redis: _FakeRedis, db) -> User:
    """Invoke the dependency directly, bypassing FastAPI's Depends machinery."""
    with patch.object(deps, "redis_client", redis), patch.object(
        deps, "UserRepository"
    ) as repo_cls, patch.object(
        deps, "decode_token", lambda t: {"sub": "1", "type": "access"}
    ):
        repo_cls.return_value.get = _AsyncReturning(_user())
        return await deps.get_current_user(_creds(token), db)


class _AsyncReturning:
    def __init__(self, value):
        self._value = value

    async def __call__(self, *a, **kw):
        return self._value


@pytest.mark.asyncio
class TestBlacklistCacheCannotUnfireARevocation:
    async def test_token_is_refused_on_the_first_check(self, db):
        """Baseline: revocation is immediate when nothing is cached."""
        token = create_access_token({"sub": "1"}, timedelta(minutes=60))
        redis = _FakeRedis()
        redis.data[f"jwt:blacklist:{token}"] = "1"

        with pytest.raises(TokenRevoked):
            await _call(token, redis, db)
        assert token in deps._blacklist_cache

    async def test_token_is_still_refused_after_the_cache_entry_ages_out(self, db):
        """THE REGRESSION. Simulates the 60s cache TTL elapsing.

        The Redis entry is deliberately still present — that is the real
        situation, since it is written with the token's remaining lifetime
        rather than the cache's 60 seconds. The pre-fix code never read it and
        authorized the request.
        """
        token = create_access_token({"sub": "1"}, timedelta(minutes=60))
        redis = _FakeRedis()
        redis.data[f"jwt:blacklist:{token}"] = "1"

        # First check populates the cache and raises.
        with pytest.raises(TokenRevoked):
            await _call(token, redis, db)
        assert token in deps._blacklist_cache

        # The entry ages past its TTL, as it does 60 real seconds later.
        deps._blacklist_cache[token] = time.time() - 1

        # The Redis blacklist is untouched and still says "revoked".
        assert redis.data[f"jwt:blacklist:{token}"] == "1"

        # Pre-fix: this returned the user. The token was accepted again.
        with pytest.raises(TokenRevoked):
            await _call(token, redis, db)

    async def test_a_stale_entry_is_replaced_not_retained(self, db):
        """The dict is written once per revoked token and never cleaned.

        Asserted on the cache because a memory leak has no other observable
        symptom: a long-lived process accumulates one ~200-byte key per logout,
        forever, with nothing at which it self-limits.

        The entry is not absent afterwards — Redis still reports the token
        revoked, so a *fresh* entry is written, replacing the stale one. The
        invariant is that the value moves forward and the key count does not
        grow, which is what distinguishes "evicted then re-cached" from
        "retained untouched".
        """
        token = create_access_token({"sub": "1"}, timedelta(minutes=60))
        redis = _FakeRedis()
        redis.data[f"jwt:blacklist:{token}"] = "1"

        with pytest.raises(TokenRevoked):
            await _call(token, redis, db)
        assert token in deps._blacklist_cache

        stale = time.time() - 1
        deps._blacklist_cache[token] = stale
        keys_before = len(deps._blacklist_cache)

        with pytest.raises(TokenRevoked):
            await _call(token, redis, db)

        # Pre-fix: the value was still the stale timestamp, because the stale
        # entry satisfied neither branch and nothing rewrote or removed it.
        assert deps._blacklist_cache[token] > stale
        # And the stale entry is never left sitting alongside a new one.
        assert len(deps._blacklist_cache) == keys_before

    async def test_entries_for_tokens_that_are_no_longer_blacklisted_are_dropped(self, db):
        """The real leak: Redis expiring must not leave a permanent key.

        A token's Redis blacklist entry is written with the token's remaining
        lifetime, so it eventually disappears. The in-process entry outlived it,
        because only a success or a re-blacklist could clear it — so the dict
        kept the key for the process's lifetime. This is the path that empties
        it.
        """
        token = create_access_token({"sub": "1"}, timedelta(minutes=60))
        redis = _FakeRedis()
        redis.data[f"jwt:blacklist:{token}"] = "1"

        with pytest.raises(TokenRevoked):
            await _call(token, redis, db)
        assert token in deps._blacklist_cache

        # Two independent conditions, both real: the entry aged out, and Redis
        # has since dropped the token (its own TTL elapsed).
        deps._blacklist_cache[token] = time.time() - 1
        redis.data.clear()

        user = await _call(token, redis, db)
        assert user.id == 1
        assert token not in deps._blacklist_cache

    async def test_a_stale_entry_still_consults_redis(self, db):
        """Pins the mechanism, not just the outcome.

        A future "optimisation" that skips Redis on a stale hit would restore
        the bypass, and the two tests above would still fail — but for the
        wrong reason. Asserting the lookup happens makes the fix's shape
        explicit: a cache miss must always reach the source of truth.
        """
        token = create_access_token({"sub": "1"}, timedelta(minutes=60))
        redis = _FakeRedis()
        redis.data[f"jwt:blacklist:{token}"] = "1"
        deps._blacklist_cache[token] = time.time() - 1

        with pytest.raises(TokenRevoked):
            await _call(token, redis, db)

        assert f"jwt:blacklist:{token}" in redis.gets

    async def test_an_unrevoked_token_is_still_accepted(self, db):
        """The fix must not make the cache fail closed.

        Evicting on a stale hit means every request after 60s goes to Redis
        again. If that path were wrong, legitimate traffic would break — so
        this is the other half of the invariant.
        """
        token = create_access_token({"sub": "1"}, timedelta(minutes=60))
        redis = _FakeRedis()  # no blacklist entry

        user = await _call(token, redis, db)
        assert user.id == 1
        assert token not in deps._blacklist_cache

    async def test_cache_hit_avoids_the_redis_round_trip(self, db):
        """Why the cache exists at all: Upstash is ~100-200ms per command.

        A fresh entry must short-circuit, or the fix would have quietly traded a
        security hole for a large latency regression on every request.
        """
        token = create_access_token({"sub": "1"}, timedelta(minutes=60))
        redis = _FakeRedis()
        redis.data[f"jwt:blacklist:{token}"] = "1"

        with pytest.raises(TokenRevoked):
            await _call(token, redis, db)
        first_round_trips = len(redis.gets)

        with pytest.raises(TokenRevoked):
            await _call(token, redis, db)

        assert len(redis.gets) == first_round_trips, "a live cache entry hit Redis"
