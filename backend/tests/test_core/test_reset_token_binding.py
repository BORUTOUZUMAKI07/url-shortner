"""A password-reset link must not survive the password it was issued against.

`reset_password` revokes the user's refresh family, which reads like it retires
the credential. It does not: the reset *token* was a pure function of
`(email, expiry)`, so it stayed valid for its full hour. An attacker who saw a
reset link could therefore wait for the owner to use it, then replay the same
link with a password of their own choosing and take the account - revoking
sessions does nothing, because they are not using a session.

The token is now bound to a fingerprint of the password it was issued against, so
the first successful reset kills it. That is deliberately stateless: no Redis
record, so no cache outage can turn into either a lockout or a bypass.

The `jti` nonce exists for a related reason: with none, two tokens minted in the
same second were byte-identical, so "resend" could not produce a genuinely new
link.
"""

import pytest
from jose import jwt

from src.identity.services import auth_service as auth_module
from src.identity.services.auth_service import AuthService
from src.shared.core.config import settings
from src.shared.core.security import (
    create_email_verification_token,
    create_password_reset_token,
    decode_token,
    reset_fingerprint,
)
from src.shared.errors import InvalidResetToken

HASH_A = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHQ$aGFzaEFh"
HASH_B = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$aGFzaEFC"


class _User:
    def __init__(self, email="me@example.com", password_hash=HASH_A, uid=1):
        self.id = uid
        self.email = email
        self.password_hash = password_hash


class _Repo:
    def __init__(self, user):
        self._user = user
        self.updates: list[dict] = []

    async def get(self, user_id):
        return self._user

    async def get_by_email(self, email):
        return self._user if self._user and self._user.email == email else None

    async def update(self, user_id, **values):
        self.updates.append(values)
        for k, v in values.items():
            setattr(self._user, k, v)
        return self._user


class _Unused:
    def __getattr__(self, name):
        async def _noop(*a, **k):
            return None

        return _noop


@pytest.fixture(autouse=True)
def _no_hashing(monkeypatch):
    """Skip the real (slow, CPU-bound) Argon2 work; the binding is the subject."""
    async def _fake(plain):
        return f"$argon2id$fake${plain}"

    monkeypatch.setattr(auth_module, "hash_password_async", _fake)
    monkeypatch.setattr(auth_module, "revoke_refresh_family", lambda uid: _noop())


async def _noop(*a, **k):
    return None


def _service(user):
    repo = _Repo(user)
    return AuthService(user_repo=repo, workspace_repo=_Unused(), audit=_Unused()), repo


class TestFingerprint:
    def test_is_stable(self):
        assert reset_fingerprint(HASH_A) == reset_fingerprint(HASH_A)

    def test_differs_per_password(self):
        assert reset_fingerprint(HASH_A) != reset_fingerprint(HASH_B)

    def test_does_not_leak_the_hash(self):
        """A fingerprint must not be usable to recover or confirm a password."""
        fp = reset_fingerprint(HASH_A)
        assert HASH_A not in fp
        assert len(fp) == 16

    def test_is_not_the_bare_hash(self):
        assert reset_fingerprint(HASH_A) != HASH_A


class TestResetTokenIsBound:
    async def test_happy_path_still_works(self):
        svc, repo = _service(_User())
        token = create_password_reset_token("me@example.com", HASH_A)
        await svc.reset_password(token, "NewPassword123!")
        assert len(repo.updates) == 1
        assert repo.updates[0]["password_hash"].endswith("NewPassword123!")

    async def test_token_for_a_different_password_is_rejected(self):
        """The core bug: a token minted against the *old* password is dead."""
        svc, repo = _service(_User(password_hash=HASH_B))
        token = create_password_reset_token("me@example.com", HASH_A)
        with pytest.raises(InvalidResetToken):
            await svc.reset_password(token, "AttackerPassword999!")
        assert repo.updates == []

    async def test_replay_after_a_successful_reset_fails(self):
        """Full takeover path, end to end."""
        user = _User()
        svc, repo = _service(user)
        token = create_password_reset_token(user.email, HASH_A)

        # Owner uses their own link first.
        await svc.reset_password(token, "OwnerPassword123!")
        assert user.password_hash.endswith("OwnerPassword123!")

        # Attacker replays the same captured link afterwards.
        with pytest.raises(InvalidResetToken):
            await svc.reset_password(token, "AttackerPassword999!")
        assert user.password_hash.endswith("OwnerPassword123!")

    async def test_legacy_token_without_a_binding_is_rejected(self):
        """Tokens minted before this change carry no `pfp`.

        They must fail closed rather than defaulting to a match on an empty
        string - otherwise the fix would be a no-op for the tokens most likely to
        be sitting in an attacker's inbox.
        """
        svc, repo = _service(_User())
        legacy = jwt.encode(
            {"sub": "me@example.com", "type": "reset",
             "exp": 9999999999, "jti": "old"},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        with pytest.raises(InvalidResetToken):
            await svc.reset_password(legacy, "Whatever123!")
        assert repo.updates == []

    async def test_wrong_token_type_still_rejected(self):
        svc, repo = _service(_User())
        verify_token = create_email_verification_token("me@example.com")
        with pytest.raises(InvalidResetToken):
            await svc.reset_password(verify_token, "Whatever123!")
        assert repo.updates == []

    async def test_unknown_email_still_raises_not_found(self):
        svc, _ = _service(_User())
        token = create_password_reset_token("nobody@example.com", HASH_A)
        from src.shared.errors import UserNotFound

        with pytest.raises(UserNotFound):
            await svc.reset_password(token, "Whatever123!")


class TestTokenUniqueness:
    def test_verification_tokens_differ(self):
        a = create_email_verification_token("me@example.com")
        b = create_email_verification_token("me@example.com")
        assert a != b

    def test_verification_tokens_carry_a_jti(self):
        payload = decode_token(create_email_verification_token("me@example.com"))
        assert payload.get("jti")

    def test_reset_tokens_differ(self):
        a = create_password_reset_token("me@example.com", HASH_A)
        b = create_password_reset_token("me@example.com", HASH_A)
        assert a != b
