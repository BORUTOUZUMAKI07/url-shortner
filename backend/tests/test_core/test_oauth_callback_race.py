"""OAuth first-sign-in race: the loser adopts the winner instead of 500ing.

Two first-time sign-ins with the same provider subject both pass the
`get_by_oauth_sub` lookup (neither INSERT has committed yet), and both try to
CREATE. The unique index on the provider subject lets exactly one win; the
loser's transaction is invalid from then on. Uncaught, that IntegrityError was
a 500 with a log line — for a user who has been staring at the provider's
consent screen the whole time. The catch rolls the loser back and re-reads the
winner's row, and skips `create_default` because the winner already created it.
"""

from contextlib import ExitStack
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError

from src.identity.services.auth_service import AuthService

SECRET = "test-secret-key-for-testing"

# No-op timing lap: the _lap closure in the real callback only exists to feed
# the request-level timing log, which is not what this test asserts on.


def _noop_lap(name: str) -> None:
    pass


class Winner:
    id = 7


class RacingOAuthRepo:
    """The loser of the race: no row by subject, no email match, CREATE clashes."""

    def __init__(self, winner: Winner):
        self.winner = winner
        self.by_sub_calls = 0
        self.create_calls = 0
        self.rolled_back = False

    async def get_by_oauth_sub(self, provider, subject):
        self.by_sub_calls += 1
        # Before CREATE: the race is still open, nobody has a row. After the
        # rollback: the winner's INSERT is committed and visible.
        if self.by_sub_calls > 1:
            return self.winner
        return None

    async def email_exists(self, email):
        return False

    async def create(self, **kwargs):
        self.create_calls += 1
        raise IntegrityError(
            'duplicate key value violates unique constraint "uq_users_github_id"',
            None,
            RuntimeError("orig"),
        )

    async def rollback(self):
        self.rolled_back = True

    async def update(self, user_id, **fields):
        pass


class NoDefaultWorkspace:
    def __init__(self):
        self.calls = 0

    async def create_default(self, user_id):
        self.calls += 1


class FakeOAuth:
    def __init__(self, info):
        self.info = info
        self.exchanged = []

    def is_configured(self):
        return True

    async def authenticate(self, code, code_verifier=None):
        self.exchanged.append((code, code_verifier))
        return self.info


class FakeRedis:
    async def eval(self, script, numkeys, *args):
        return ["state-sentinel", "code-verifier"]

    async def setex(self, key, ttl, value):
        pass


async def _run(provider, repo, workspace_repo, info):
    svc = AuthService(user_repo=repo, workspace_repo=workspace_repo)
    with ExitStack() as stack:
        stack.enter_context(patch("src.identity.services.auth_service.redis_client", FakeRedis()))
        stack.enter_context(patch("src.shared.core.security.settings.SECRET_KEY", SECRET))
        stack.enter_context(patch("src.shared.core.security.settings.ALGORITHM", "HS256"))
        # Await inside the context: returning the coroutine out of the with
        # block would tear down the patches before the caller awaits it.
        return await svc._run_oauth_callback(  # noqa: SLF001 - direct test of the race branch
            provider,
            FakeOAuth(info),
            "one-time-code",
            "csrf-state",
            _noop_lap,
        )


async def test_losing_creator_adopts_winners_row_and_skips_default_workspace():
    info = {"id": "gh_123", "email": "racer@example.com", "verified_email": True}
    repo = RacingOAuthRepo(winner=Winner())
    workspace_repo = NoDefaultWorkspace()

    token = await _run("github", repo, workspace_repo, info)

    assert repo.create_calls == 1
    assert repo.rolled_back, "the loser's failed transaction must be rolled back"
    assert repo.by_sub_calls == 2, "after the rollback the winner must be re-fetched by subject"
    assert workspace_repo.calls == 0, "create_default is the winner's job; the loser must not duplicate it"
    # The request still succeeds — the user gets a session as the winner.
    assert token.access_token
    assert token.refresh_token


async def test_losing_creator_fails_cleanly_if_winner_vanished():
    class VanishingRepo(RacingOAuthRepo):
        async def get_by_oauth_sub(self, provider, subject):
            self.by_sub_calls += 1
            return None  # the winner rolled back too; nothing to adopt

    from src.shared.errors import OAuthFailed

    info = {"id": "gh_123", "email": "racer@example.com", "verified_email": True}
    with pytest.raises(OAuthFailed):
        await _run("github", VanishingRepo(winner=Winner()), NoDefaultWorkspace(), info)
