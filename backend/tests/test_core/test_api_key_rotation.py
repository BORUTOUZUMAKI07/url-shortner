"""API-key rotation ordering: the replacement must exist before the old key dies.

The previous code revoked the old key first, then generated and hashed the new
one. Any failure in that second half — a DB blip on create, a crash between the
two statements — left the user with no working key at all until they generated
one manually. The Argon2 hash is deliberately computed before any DB write.
"""
from unittest.mock import AsyncMock

import pytest

from src.identity.services.api_key_service import APIKeyService
from src.shared.errors import NotFoundError


class OldKeyRow:
    id = 5
    user_id = 7
    name = "prod-key"
    prefix = "oldpref"
    expires_at = None


class NewKeyRow:
    def __init__(self, **kwargs):
        self.user_id = kwargs.get("user_id")
        self.name = kwargs.get("name")
        self.prefix = kwargs.get("prefix")
        self.key_hash = kwargs.get("key_hash")
        self.expires_at = kwargs.get("expires_at")


class RecordingKeyRepo:
    """Records the order of repo calls so the fix can be pinned to it."""

    def __init__(self, create_raises=None):
        self.calls = []
        self.create_raises = create_raises

    async def get(self, id):
        self.calls.append("get")
        return OldKeyRow()

    async def create(self, **kwargs):
        self.calls.append("create")
        if self.create_raises:
            raise self.create_raises
        return NewKeyRow(**kwargs)

    async def revoke(self, id, user_id):
        self.calls.append("revoke")
        return None

    async def get_user_keys(self, user_id):
        return []


async def _rotate(repo):
    return await APIKeyService(repo=repo, user_repo=AsyncMock()).rotate(5, 7)


async def test_rotation_creates_new_key_before_revoking_old():
    repo = RecordingKeyRepo()
    new_key, raw_key = await _rotate(repo)

    assert repo.calls == ["get", "create", "revoke"], (
        "rotation must revoke only after the replacement row exists; "
        f"got call order {repo.calls}"
    )
    assert new_key.user_id == 7
    assert new_key.name == "prod-key"
    assert new_key.expires_at is None
    assert new_key.prefix == raw_key[:8]
    assert new_key.key_hash != raw_key


async def test_rotation_failure_leaves_old_key_intact():
    """If the new key cannot be materialised, the old key must still work.

    On the unfixed code `revoke` ran first, so a failed create still destroyed
    the old key — this assertion fails there with 'revoke' present in the calls.
    """
    repo = RecordingKeyRepo(create_raises=RuntimeError("db blip"))
    with pytest.raises(RuntimeError):
        await _rotate(repo)
    assert "revoke" not in repo.calls, "old key must survive a failed rotation"
    assert repo.calls == ["get", "create"]


async def test_rotation_of_foreign_key_is_rejected():
    class ForeignKeyRepo(RecordingKeyRepo):
        async def get(self, id):
            self.calls.append("get")
            row = OldKeyRow()
            row.user_id = 999
            return row

    repo = ForeignKeyRepo()
    with pytest.raises(NotFoundError):
        await _rotate(repo)
    assert repo.calls == ["get"], "a foreign key must not be touched or revoked"
