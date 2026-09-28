"""Admin self-service guards, at the service level (no DB needed).

`POST /admin/seed` was open to any authenticated user, and
`PATCH /admin/users/{id}/toggle-superadmin` had no guard at all, so an admin
could demote themselves and leave the platform with no way back in. The route
tests cover the HTTP surface; these pin the service invariants directly, which
is where a future caller would otherwise bypass them.
"""

import pytest

from src.admin.services.admin_service import AdminService
from src.shared.errors import BadRequestError, NotFoundError


class _User:
    def __init__(self, id, is_superadmin=False, is_active=True):
        self.id = id
        self.email = f"u{id}@example.com"
        self.is_superadmin = is_superadmin
        self.is_active = is_active


class _UserRepo:
    def __init__(self, users):
        self.users = {u.id: u for u in users}
        self.updated: list[tuple[int, dict]] = []
        self.deleted: list[int] = []

    async def get(self, user_id):
        return self.users.get(user_id)

    async def get_by(self, **filters):
        for u in self.users.values():
            if all(getattr(u, k) == v for k, v in filters.items()):
                return u
        return None

    async def update(self, user_id, **values):
        self.updated.append((user_id, values))
        obj = self.users[user_id]
        for k, v in values.items():
            setattr(obj, k, v)
        return obj

    async def delete(self, user_id):
        self.deleted.append(user_id)
        self.users.pop(user_id, None)
        return True

    async def count_superadmins(self):
        return sum(1 for u in self.users.values() if u.is_superadmin)

    async def count(self):
        return len(self.users)


class _Other:
    def __init__(self):
        self.counts = {"Workspace": 0, "URL": 0}

    async def count(self):
        return 0

    async def list_all(self, skip=0, limit=100):
        return []


def _service(users):
    repo = _UserRepo(users)
    return AdminService(user_repo=repo, workspace_repo=_Other(), url_repo=_Other()), repo


class TestLastActiveAdminGuard:
    async def test_cannot_demote_the_only_superadmin(self):
        svc, repo = _service([_User(1, is_superadmin=True)])
        with pytest.raises(BadRequestError, match="last active superadmin"):
            await svc.toggle_superadmin(1, acting_user_id=99)
        assert repo.updated == []

    async def test_cannot_deactivate_the_only_superadmin(self):
        svc, repo = _service([_User(1, is_superadmin=True)])
        with pytest.raises(BadRequestError, match="last active superadmin"):
            await svc.toggle_active(1, acting_user_id=99)
        assert repo.updated == []

    async def test_cannot_delete_the_only_superadmin(self):
        svc, repo = _service([_User(1, is_superadmin=True)])
        with pytest.raises(BadRequestError, match="last active superadmin"):
            await svc.delete_user(1, acting_user_id=99)
        assert repo.deleted == []

    async def test_cannot_demote_another_admin_when_alone(self):
        """A second superadmin existing is what makes this safe."""
        svc, repo = _service([_User(1), _User(2, is_superadmin=True)])
        with pytest.raises(BadRequestError, match="last active superadmin"):
            await svc.toggle_superadmin(2, acting_user_id=1)
        assert repo.updated == []

    async def test_allowed_once_a_second_admin_exists(self):
        svc, repo = _service([_User(1, is_superadmin=True), _User(2, is_superadmin=True)])
        updated = await svc.toggle_superadmin(2, acting_user_id=1)
        assert updated.is_superadmin is False
        assert repo.updated == [(2, {"is_superadmin": False})]

    async def test_cannot_demote_self_even_with_another_admin(self):
        svc, repo = _service([_User(1, is_superadmin=True), _User(2, is_superadmin=True)])
        with pytest.raises(BadRequestError, match="your own"):
            await svc.toggle_superadmin(1, acting_user_id=1)

    async def test_cannot_delete_self_as_superadmin_gets_actionable_message(self):
        """The self-delete check must run before the last-admin guard, otherwise
        a superadmin deleting themselves gets the generic 'ask another admin'
        wording and never learns that deactivation is the right action."""
        svc, repo = _service([_User(1, is_superadmin=True), _User(2, is_superadmin=True)])
        with pytest.raises(BadRequestError, match="deactivate it instead"):
            await svc.delete_user(1, acting_user_id=1)
        assert repo.deleted == []

    async def test_cannot_delete_self_as_regular_admin(self):
        svc, repo = _service([_User(1, is_superadmin=True), _User(2)])
        with pytest.raises(BadRequestError, match="deactivate it instead"):
            await svc.delete_user(2, acting_user_id=2)
        assert repo.deleted == []

    async def test_non_admin_targets_are_unrestricted(self):
        """The guard must not block ordinary moderation of regular users."""
        svc, repo = _service([_User(1, is_superadmin=True), _User(2)])
        updated = await svc.toggle_active(2, acting_user_id=1)
        assert updated.is_active is False
        assert repo.updated == [(2, {"is_active": False})]

    async def test_deactivating_revokes_sessions(self, monkeypatch):
        svc, repo = _service([_User(1, is_superadmin=True), _User(2)])
        revoked: list[int] = []

        async def _revoke(user_id):
            revoked.append(user_id)

        monkeypatch.setattr(
            "src.admin.services.admin_service.revoke_refresh_family", _revoke
        )
        await svc.toggle_active(2, acting_user_id=1)
        assert revoked == [2]

    async def test_reactivation_does_not_revoke(self, monkeypatch):
        svc, repo = _service([_User(1, is_superadmin=True), _User(2, is_active=False)])
        revoked: list[int] = []

        async def _revoke(user_id):
            revoked.append(user_id)

        monkeypatch.setattr(
            "src.admin.services.admin_service.revoke_refresh_family", _revoke
        )
        await svc.toggle_active(2, acting_user_id=1)
        assert revoked == []

    async def test_unknown_user_raises_not_found(self):
        svc, _ = _service([])
        with pytest.raises(NotFoundError):
            await svc.toggle_superadmin(4242, acting_user_id=1)


class TestSeedSuperadmin:
    async def test_seed_refuses_when_one_already_exists(self):
        svc, repo = _service([_User(1, is_superadmin=True)])
        with pytest.raises(BadRequestError, match="already exists"):
            await svc.seed_superadmin(_User(2))
        assert repo.updated == []

    async def test_seed_promotes_first_admin(self):
        svc, repo = _service([_User(1), _User(2)])
        assert await svc.seed_superadmin(_User(2)) == "u2@example.com"
        assert repo.updated == [(2, {"is_superadmin": True})]
