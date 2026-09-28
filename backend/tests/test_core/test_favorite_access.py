"""`FavoriteService.add` must verify the caller can reach the URL's workspace.

The original `add` took any `url_id` and created the row, so any authenticated
user could favourite a URL belonging to a workspace they have no access to —
and, just as importantly, the successful 200 confirmed the URL existed. The
workspace check returns `Workspace | None` rather than raising, so simply
awaiting it is not enough; these tests pin the checked behaviour.
"""

import pytest

from src.links.models.url import URLStatus
from src.links.services.favorite_service import FavoriteService
from src.shared.errors import ConflictError, URLNotFound


class _URL:
    def __init__(self, workspace_id=1, status=URLStatus.active):
        self.id = 7
        self.workspace_id = workspace_id
        self.status = status


class _FavRepo:
    def __init__(self, already=False):
        self.already = already
        self.created: list[tuple[int, int]] = []

    async def is_favorited(self, user_id, url_id):
        return self.already

    async def create(self, user_id, url_id):
        self.created.append((user_id, url_id))
        return ("fav", user_id, url_id)

    async def remove(self, user_id, url_id):
        return True


class _UrlRepo:
    def __init__(self, url):
        self.url = url

    async def get(self, url_id):
        return self.url


class _WorkspaceRepo:
    def __init__(self, accessible=True):
        self.accessible = accessible
        self.checked: list[tuple[int, int]] = []

    async def verify_access(self, workspace_id, user_id):
        # Mirrors the real repository: returns the workspace or None.
        self.checked.append((workspace_id, user_id))
        return object() if self.accessible else None


_DEFAULT = object()  # sentinel: `None` is a meaningful value (missing URL) here


def _service(url=_DEFAULT, accessible=True, already=False):
    fav = _FavRepo(already)
    ws = _WorkspaceRepo(accessible)
    return (
        FavoriteService(repo=fav, url_repo=_UrlRepo(_URL() if url is _DEFAULT else url),
                        workspace_repo=ws),
        fav,
        ws,
    )


class TestFavoriteAddWorkspaceAccess:
    async def test_rejects_url_in_inaccessible_workspace(self):
        svc, fav, ws = _service(accessible=False)
        with pytest.raises(URLNotFound):
            await svc.add(7, user_id=99)
        assert fav.created == []
        # The check actually ran, and ran on the URL's own workspace.
        assert ws.checked == [(1, 99)]

    async def test_allows_url_in_accessible_workspace(self):
        svc, fav, _ = _service(accessible=True)
        assert await svc.add(7, user_id=1) is not None
        assert fav.created == [(1, 7)]

    async def test_missing_url(self):
        svc, fav, _ = _service(url=None)
        with pytest.raises(URLNotFound):
            await svc.add(7, user_id=1)
        assert fav.created == []

    async def test_deleted_url(self):
        svc, fav, _ = _service(url=_URL(status=URLStatus.deleted))
        with pytest.raises(URLNotFound):
            await svc.add(7, user_id=1)
        assert fav.created == []

    async def test_workspaceless_url_needs_no_workspace_check(self):
        """A URL with no workspace (shouldn't normally happen) skips the check
        rather than being rejected — the URL row itself is the only scope."""
        svc, fav, ws = _service(url=_URL(workspace_id=None))
        assert await svc.add(7, user_id=1) is not None
        assert ws.checked == []

    async def test_duplicate_still_conflicts_after_access_check(self):
        """Ordering matters: the access check runs first, so a user who cannot
        reach the URL learns nothing from the conflict message."""
        svc, _, ws = _service(accessible=False, already=True)
        with pytest.raises(URLNotFound):
            await svc.add(7, user_id=99)
        assert ws.checked == [(1, 99)]

    async def test_duplicate_reports_conflict_for_permitted_user(self):
        svc, _, _ = _service(accessible=True, already=True)
        with pytest.raises(ConflictError):
            await svc.add(7, user_id=1)
