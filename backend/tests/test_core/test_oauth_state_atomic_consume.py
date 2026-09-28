"""The OAuth callback's state + PKCE consume must be one atomic round trip.

oauth_callback used to mget() the two keys and then delete_many() them: two serial
Upstash REST calls, with a window between them in which a crash left the state
replayable. It now runs a single Lua script that reads and deletes together.

Two things are verified here, and they need different tools:

  * the SCRIPT's real behaviour (reads, deletes, reports a missing key, survives
    the reject path) can only be established against a real Redis — a fake's
    eval() returns a canned value and executes nothing. These tests use the real
    RedisAdapter, so they cover the Upstash command encoding too.
  * that oauth_callback issues exactly ONE command for the consume is pinned
    against a double, so it still holds when no Redis is available.
"""
from __future__ import annotations

import os
import uuid

import pytest
import redis.asyncio as aioredis

from src.identity.services.auth_service import _CONSUME_OAUTH_STATE_LUA
from src.shared.core.config import settings
from src.shared.core.redis import RedisAdapter

_TESTCONTAINERS = os.environ.get("_USE_TESTCONTAINERS") == "1"

requires_real_redis = pytest.mark.skipif(
    not _TESTCONTAINERS,
    reason="needs the testcontainers Redis; run with --use-testcontainers",
)


def _real_adapter() -> RedisAdapter:
    return RedisAdapter(aioredis.from_url(settings.REDIS_URL, decode_responses=True))


def _keys() -> tuple[str, str]:
    """Unique keys per test so a real Redis is never clobbered."""
    tag = uuid.uuid4().hex
    return f"test:oauth:state:{tag}", f"test:oauth:pkce:{tag}"


@requires_real_redis
async def test_returns_both_values_and_deletes_both_keys() -> None:
    adapter = _real_adapter()
    state_key, pkce_key = _keys()
    await adapter.setex(state_key, 60, "state-value")
    await adapter.setex(pkce_key, 60, "verifier-value")

    result = await adapter.eval(_CONSUME_OAUTH_STATE_LUA, 2, state_key, pkce_key)

    assert result[0] == "state-value"
    assert result[1] == "verifier-value"
    assert await adapter.get(state_key) is None, "state key was not consumed"
    assert await adapter.get(pkce_key) is None, "pkce key was not consumed"


@requires_real_redis
async def test_missing_pkce_reports_none_not_false() -> None:
    """PKCE is optional in the flow, so the provider must be handed None.

    Lua cannot store nil in a table, so the script reports a missing key as
    false. If that leaked through as False, code_verifier would be a bool and a
    provider doing `if code_verifier` would send a PKCE parameter of "false".
    """
    adapter = _real_adapter()
    state_key, pkce_key = _keys()
    await adapter.setex(state_key, 60, "state-value")

    result = await adapter.eval(_CONSUME_OAUTH_STATE_LUA, 2, state_key, pkce_key)

    assert result[0] == "state-value"
    assert not result[1], "a missing pkce must come back falsy"
    assert await adapter.get(state_key) is None


@requires_real_redis
async def test_missing_state_still_deletes_a_leaked_pkce() -> None:
    """The reject path must consume both keys.

    A state that fails CSRF must not stay valid for a retry, and a PKCE record
    left behind without its state is dead weight — but deleting only what was
    read would strand it.
    """
    adapter = _real_adapter()
    state_key, pkce_key = _keys()
    await adapter.setex(pkce_key, 60, "verifier-value")

    result = await adapter.eval(_CONSUME_OAUTH_STATE_LUA, 2, state_key, pkce_key)

    assert not result[0], "no state present must read as falsy"
    assert result[1] == "verifier-value"
    assert await adapter.get(pkce_key) is None, "pkce survived a rejected callback"


@requires_real_redis
async def test_all_keys_absent_is_safe() -> None:
    """Both keys already gone (expired, or a replayed callback) must not error."""
    adapter = _real_adapter()
    state_key, pkce_key = _keys()

    result = await adapter.eval(_CONSUME_OAUTH_STATE_LUA, 2, state_key, pkce_key)

    assert not result[0]
    assert not result[1]


@requires_real_redis
async def test_second_consume_finds_nothing() -> None:
    """Single-use: the script is atomic, so a replay cannot re-read the state."""
    adapter = _real_adapter()
    state_key, pkce_key = _keys()
    await adapter.setex(state_key, 60, "state-value")
    await adapter.setex(pkce_key, 60, "verifier-value")

    first = await adapter.eval(_CONSUME_OAUTH_STATE_LUA, 2, state_key, pkce_key)
    second = await adapter.eval(_CONSUME_OAUTH_STATE_LUA, 2, state_key, pkce_key)

    assert first[0] == "state-value"
    assert not second[0], "state was readable twice — the consume is not atomic"


class _RecordingRedis:
    """Records commands; eval returns a fixed pair so no Lua is executed."""

    def __init__(self) -> None:
        self.commands: list[tuple[str, tuple]] = []
        self.store: dict[str, str] = {}

    async def eval(self, script: str, numkeys: int, *args):
        self.commands.append(("eval", (numkeys, *args)))
        return ("state-value", None)

    async def mget(self, *keys):
        self.commands.append(("mget", keys))
        return tuple(self.store.get(k) for k in keys)

    async def delete_many(self, *keys):
        self.commands.append(("delete_many", keys))
        for k in keys:
            self.store.pop(k, None)
        return len(keys)

    async def setex(self, key: str, ttl: int, value: str):
        self.store[key] = value
        return True


@pytest.fixture
def recording_redis(monkeypatch: pytest.MonkeyPatch) -> _RecordingRedis:
    fake = _RecordingRedis()
    monkeypatch.setattr("src.identity.services.auth_service.redis_client", fake)
    return fake


def _stub_service(recorder: _RecordingRedis, state_value: str = "state-value"):
    """A service with just enough surface for oauth_callback to reach the consume."""
    import src.identity.services.auth_service as mod

    class _Repo:
        async def get_by_oauth_sub(self, provider, subject):
            raise AssertionError("stop before user lookup; this test only covers the consume")

    class _OAuth:
        is_configured = staticmethod(lambda: True)
        provider = "google"

        async def authenticate(self, code, code_verifier=None):
            raise AssertionError("stop after the consume; this test only covers the consume")

    svc = mod.AuthService.__new__(mod.AuthService)
    svc.user_repo = _Repo()
    svc._oauth_registry_override = _OAuth
    return svc


async def test_callback_consumes_state_in_a_single_command(
    recording_redis: _RecordingRedis,
) -> None:
    """Mechanism pin, so the one-round-trip property is not silently reverted.

    Runs without Docker: the double never executes Lua, so this asserts only that
    the callback issues one command (eval) rather than mget + delete_many.
    """
    from src.identity.services.sso import SSOProviderRegistry

    original = SSOProviderRegistry.get
    SSOProviderRegistry.get = staticmethod(lambda provider: _StubOAuth())  # type: ignore[assignment]
    try:
        svc = _stub_service(recording_redis)
        with pytest.raises(Exception):  # noqa: B017 - we only care where it failed
            await svc.oauth_callback("google", "the-code", "the-state")
    finally:
        SSOProviderRegistry.get = original  # type: ignore[assignment]

    kinds = [kind for kind, _ in recording_redis.commands]
    assert kinds == ["eval"], f"expected one atomic eval, got {kinds}"
    numkeys, key1, key2 = recording_redis.commands[0][1]
    assert numkeys == 2
    assert key1.endswith("the-state") and key2.endswith("the-state")


class _StubOAuth:
    provider = "google"

    @staticmethod
    def is_configured() -> bool:
        return True

    async def authenticate(self, code, code_verifier=None):  # noqa: ARG002
        raise AssertionError("consume already validated; must not be reached")
