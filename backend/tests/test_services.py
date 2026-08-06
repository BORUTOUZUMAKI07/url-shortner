from unittest.mock import AsyncMock

import pytest

from src.identity.models.user import User
from src.identity.services.auth_service import AuthService
from src.links.models.url import URLStatus
from src.links.schemas.url import URLCreate
from src.links.services.url_service import URLService
from src.shared.errors import EmailAlreadyExists, InvalidCredentials
from src.shared.errors.url import URLNotFound
from src.workspaces.services.workspace_service import WorkspaceService


@pytest.mark.asyncio
async def test_auth_register_success(db, mock_repos):
    mock_repos.user_repo.email_exists.return_value = False
    mock_repos.user_repo.create.return_value = User(id=1, email="new@example.com", is_verified=False)
    service = AuthService(mock_repos.user_repo, mock_repos.workspace_repo)
    user = await service.register(email="new@example.com", password="newpass123")
    assert user.email == "new@example.com"
    assert user.is_verified is False


@pytest.mark.asyncio
async def test_auth_register_duplicate_email(db, mock_repos, test_user):
    mock_repos.user_repo.email_exists.return_value = True
    service = AuthService(mock_repos.user_repo, mock_repos.workspace_repo)
    with pytest.raises(EmailAlreadyExists):
        await service.register(email=test_user.email, password="newpass123")


@pytest.mark.asyncio
async def test_auth_login_success(db, mock_repos, test_user):
    mock_repos.user_repo.get_by_email.return_value = test_user
    service = AuthService(mock_repos.user_repo, mock_repos.workspace_repo)
    token = await service.login(email=test_user.email, password="testpass123")
    assert token.access_token is not None
    assert token.token_type == "bearer"


@pytest.mark.asyncio
async def test_auth_login_wrong_password(db, mock_repos, test_user):
    mock_repos.user_repo.get_by_email.return_value = test_user
    service = AuthService(mock_repos.user_repo, mock_repos.workspace_repo)
    with pytest.raises(InvalidCredentials):
        await service.login(email=test_user.email, password="wrongpass")


@pytest.mark.asyncio
async def test_url_create_success(db, mock_repos, test_user, test_workspace, mock_audit, mock_webhooks, mock_event_dispatcher):
    created_url = AsyncMock()
    created_url.short_code = "abc123"
    created_url.original_url = "https://example.com"
    created_url.workspace_id = test_workspace.id
    created_url.user_id = test_user.id
    created_url.status = URLStatus.active
    created_url.tags = []
    mock_repos.url_repo.create.return_value = created_url
    mock_repos.url_repo.get.return_value = created_url
    service = URLService(db, mock_repos.url_repo, mock_repos.workspace_repo,
                         mock_repos.folder_repo, mock_repos.tag_repo,
                         mock_audit, mock_webhooks, mock_event_dispatcher)
    payload = URLCreate(
        original_url="https://example.com",
        workspace_id=test_workspace.id,
    )
    url = await service.create(payload, user_id=test_user.id)
    assert url.original_url == "https://example.com"


@pytest.mark.asyncio
async def test_url_get_not_found(db, mock_repos, test_user, mock_audit, mock_webhooks, mock_event_dispatcher):
    mock_repos.workspace_repo.verify_access.return_value = True
    mock_repos.url_repo.get.return_value = None
    service = URLService(db, mock_repos.url_repo, mock_repos.workspace_repo,
                         mock_repos.folder_repo, mock_repos.tag_repo,
                         mock_audit, mock_webhooks, mock_event_dispatcher)
    with pytest.raises(URLNotFound):
        await service.get(id=99999, user_id=test_user.id)


@pytest.mark.asyncio
async def test_url_delete(db, mock_repos, test_user, test_url, mock_audit, mock_webhooks, mock_event_dispatcher):
    mock_repos.workspace_repo.verify_access.return_value.__aenter__ = AsyncMock()
    mock_repos.workspace_repo.verify_access.return_value = True
    mock_repos.url_repo.get.return_value = test_url
    service = URLService(db, mock_repos.url_repo, mock_repos.workspace_repo,
                         mock_repos.folder_repo, mock_repos.tag_repo,
                         mock_audit, mock_webhooks, mock_event_dispatcher)
    await service.delete(id=test_url.id, user_id=test_user.id)
    mock_repos.url_repo.soft_delete.assert_called_once_with(test_url.id)


@pytest.mark.asyncio
async def test_workspace_create(db, mock_repos, test_user, mock_audit, mock_webhooks):
    mock_repos.member_repo.add_member = AsyncMock()
    mock_repos.repo = mock_repos.workspace_repo
    created_ws = AsyncMock(id=1, owner_id=test_user.id)
    created_ws.name = "New Workspace"
    mock_repos.repo.create.return_value = created_ws
    service = WorkspaceService(mock_repos.workspace_repo, mock_repos.member_repo,
                               mock_repos.invite_repo, mock_repos.user_repo,
                               mock_audit, mock_webhooks)
    ws = await service.create(name="New Workspace", user_id=test_user.id)
    assert ws.name == "New Workspace"
    assert ws.owner_id == test_user.id


@pytest.mark.asyncio
async def test_workspace_list(db, mock_repos, test_user, test_workspace, mock_audit, mock_webhooks):
    mock_repos.workspace_repo.get_user_workspaces.return_value = [test_workspace]
    service = WorkspaceService(mock_repos.workspace_repo, mock_repos.member_repo,
                               mock_repos.invite_repo, mock_repos.user_repo,
                               mock_audit, mock_webhooks)
    workspaces = await service.list(user_id=test_user.id)
    assert len(workspaces) == 1
    assert workspaces[0].id == test_workspace.id
