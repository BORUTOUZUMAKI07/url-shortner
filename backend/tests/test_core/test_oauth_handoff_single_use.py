"""The OAuth handoff code must be redeemable exactly once.

create_oauth_handoff() stores the refresh token under a 120s, single-use key and
hands the code to the browser in a redirect URL. exchange_oauth_handoff() is the
only thing standing between that code and a second, attacker-triggered session,
so "one-time" has to mean one-time even under concurrency.
"""
from __future__ import annotations

import asyncio

import pytest

from src.identity.services import auth_service
from src.identity.services.auth_service import AuthService


class _RacyRedis:
    """A Redis double that models the real command boundaries honestly.

    get() and delete() are two separate commands, so a second caller can read a
    value in the window between them. getdel() is one atomic command, so it
    cannot. Every method yields via asyncio.sleep(0) so the interleaving is
    deterministic under test rather than a lucky race.
    """

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.calls: list[tuple[str, str]] = []

    async def get(self, key: str):
        await asyncio.sleep(0)
        self.calls.append(("get", key))
        return self.store.get(key)

    async def delete(self, key: str):
        await asyncio.sleep(0)
        self.calls.append(("delete", key))
        self.store.pop(key, None)

    async def getdel(self, key: str):
        await asyncio.sleep(0)
        self.calls.append(("getdel", key))
        return self.store.pop(key, None)

    async def setex(self, key: str, ttl: int, value: str):
        self.calls.append(("setex", key))
        self.store[key] = value


@pytest.fixture
def redis_double(monkeypatch: pytest.MonkeyPatch) -> _RacyRedis:
    fake = _RacyRedis()
    monkeypatch.setattr(auth_service, "redis_client", fake)
    return fake


def _svc() -> AuthService:
    return AuthService.__new__(AuthService)


async def test_concurrent_exchange_of_same_code_has_exactly_one_winner(
    redis_double: _RacyRedis,
) -> None:
    """Two simultaneous redemptions of the same handoff code.

    Against the old get()+delete() implementation both callers read the token
    before either delete landed, so the single-use code yielded two sessions.
    """
    svc = _svc()
    code = await svc.create_oauth_handoff("refresh-token-value")

    results = await asyncio.gather(
        svc.exchange_oauth_handoff(code),
        svc.exchange_oauth_handoff(code),
        return_exceptions=True,
    )

    winners = [r for r in results if isinstance(r, str)]
    assert len(winners) == 1, f"expected exactly one winner, got {len(winners)}: {results!r}"
    assert winners[0] == "refresh-token-value"

    losers = [r for r in results if not isinstance(r, str)]
    assert len(losers) == 1, "the losing caller must raise, not silently return nothing"
    assert type(losers[0]).__name__ == "InvalidToken"


async def test_exchange_uses_atomic_getdel_not_get_plus_delete(
    redis_double: _RacyRedis,
) -> None:
    """Pins the mechanism, not just the outcome.

    A test double whose get() and delete() are already atomic would pass the
    race above even with the vulnerable code, so assert the command used.
    """
    svc = _svc()
    code = await svc.create_oauth_handoff("refresh-token-value")
    redis_double.calls.clear()

    assert await svc.exchange_oauth_handoff(code) == "refresh-token-value"

    kinds = [kind for kind, _ in redis_double.calls]
    assert kinds == ["getdel"], f"expected a single atomic getdel, got {kinds}"


async def test_second_exchange_after_success_is_rejected(redis_double: _RacyRedis) -> None:
    svc = _svc()
    code = await svc.create_oauth_handoff("refresh-token-value")

    assert await svc.exchange_oauth_handoff(code) == "refresh-token-value"
    with pytest.raises(Exception):  # noqa: B017 - InvalidToken is the contract
        await svc.exchange_oauth_handoff(code)


async def test_empty_code_rejected_without_touching_redis(redis_double: _RacyRedis) -> None:
    svc = _svc()
    with pytest.raises(Exception):  # noqa: B017 - InvalidToken is the contract
        await svc.exchange_oauth_handoff("")
    assert redis_double.calls == [], "an empty code must not reach Redis at all"


async def test_unknown_code_rejected(redis_double: _RacyRedis) -> None:
    svc = _svc()
    with pytest.raises(Exception):  # noqa: B017 - InvalidToken is the contract
        await svc.exchange_oauth_handoff("never-issued")
