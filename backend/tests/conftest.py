import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from src.identity.models.user import User
from src.links.models.url import URL, URLStatus
from src.shared.core.security import hash_password
from src.workspaces.models.workspace import Workspace


def pytest_addoption(parser):
    parser.addoption(
        "--use-testcontainers",
        action="store_true",
        default=False,
        help="Use Docker testcontainers for Postgres, MongoDB, and Redis",
    )


def pytest_sessionstart(session):
    if session.config.getoption("--use-testcontainers"):
        from tests.testcontainers import start_containers
        start_containers()
    # Clean test data once at session start — only ever runs against
    # testcontainers, never against the real .env database.
    _clean_db_once()


def _clean_db_once():
    # Hard guard: never truncate anything unless testcontainers are active.
    # _USE_TESTCONTAINERS=1 is set ONLY by tests/testcontainers.start_containers(),
    # which redirects env vars to local Docker containers before this runs.
    if os.environ.get("_USE_TESTCONTAINERS") != "1":
        return
    try:
        from src.shared.core.config import settings
        engine = create_async_engine(settings.ASYNC_DATABASE_URI, echo=False, poolclass=NullPool)
        async def _truncate():
            conn = await engine.connect()
            await conn.execute(text("TRUNCATE TABLE urls, workspace_invites, workspace_members, workspaces, users CASCADE"))
            await conn.commit()
            await conn.close()
            await engine.dispose()
        asyncio.run(_truncate())
    except Exception:
        pass  # DB might not be available yet


def pytest_sessionfinish(session):
    if os.environ.get("_USE_TESTCONTAINERS") == "1":
        from tests.testcontainers import stop_containers
        stop_containers()


_test_engine = None


def _get_test_engine():
    global _test_engine
    if _test_engine is None:
        from src.shared.core.config import settings
        _test_engine = create_async_engine(
            settings.ASYNC_DATABASE_URI,
            echo=False,
            poolclass=NullPool,
        )
    return _test_engine


@pytest_asyncio.fixture
async def db():
    if os.environ.get("_USE_TESTCONTAINERS") != "1":
        pytest.fail(
            "DB-backed tests require --use-testcontainers (Docker). "
            "Refusing to connect to the real .env database. Never run the full suite without it."
        )
    engine = _get_test_engine()
    conn = await engine.connect()
    await conn.begin()
    session = AsyncSession(bind=conn, expire_on_commit=False, autoflush=False)
    yield session
    await session.close()
    await conn.rollback()
    await conn.close()


@pytest_asyncio.fixture
async def test_user(db: AsyncSession):
    user = User(
        email="test@example.com",
        password_hash=hash_password("testpass123"),
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_workspace(db: AsyncSession, test_user: User):
    ws = Workspace(name="Test Workspace", owner_id=test_user.id)
    db.add(ws)
    await db.flush()
    await db.refresh(ws)
    return ws


@pytest_asyncio.fixture
async def test_url(db: AsyncSession, test_user: User, test_workspace: Workspace):
    url = URL(
        short_code="test123",
        original_url="https://example.com",
        user_id=test_user.id,
        workspace_id=test_workspace.id,
        status=URLStatus.active,
    )
    db.add(url)
    await db.flush()
    await db.refresh(url)
    return url


@pytest_asyncio.fixture(autouse=True)
async def fast_password_hashing():
    from passlib.context import CryptContext

    import src.shared.core.security as _sec
    fast_ctx = CryptContext(schemes=["sha256_crypt"], sha256_crypt__rounds=1000)
    original = _sec.pwd_context
    _sec.pwd_context = fast_ctx
    yield
    _sec.pwd_context = original


@pytest_asyncio.fixture(autouse=True)
async def mock_external_services():
    import contextlib
    patches = [
        patch("src.identity.services.auth_service.EmailService.send_verification_email", AsyncMock()),
        patch("src.identity.services.auth_service.EmailService.send_password_reset", AsyncMock()),
        patch("src.links.services.url_service.delete_url_cache", AsyncMock()),
        patch("src.links.services.url_service.EventDispatcher", AsyncMock()),
        patch("src.workspaces.services.workspace_service.AuditService", AsyncMock()),
        patch("src.workspaces.services.workspace_service.WebhookService", AsyncMock()),
    ]
    if os.environ.get("_USE_TESTCONTAINERS") != "1":
        redis_mock = AsyncMock(spec=["get"])
        redis_mock.get.return_value = None
        patches.insert(0, patch("src.identity.services.auth_service.redis_client", redis_mock))
        patches.insert(0, patch("src.shared.core.deps.redis_client", redis_mock))
        patches.insert(0, patch("src.shared.core.api_key_auth.redis_client", redis_mock))
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        yield


@pytest_asyncio.fixture
async def mock_repos():
    from src.identity.repositories.user_repository import UserRepository
    from src.links.repositories.folder_repository import FolderRepository
    from src.links.repositories.tag_repository import TagRepository
    from src.links.repositories.url_repository import URLRepository
    from src.workspaces.repositories.workspace_invite_repository import WorkspaceInviteRepository
    from src.workspaces.repositories.workspace_member_repository import WorkspaceMemberRepository
    from src.workspaces.repositories.workspace_repository import WorkspaceRepository

    class MockRepos:
        user_repo = AsyncMock(spec=UserRepository)
        url_repo = AsyncMock(spec=URLRepository)
        workspace_repo = AsyncMock(spec=WorkspaceRepository)
        folder_repo = AsyncMock(spec=FolderRepository)
        tag_repo = AsyncMock(spec=TagRepository)
        member_repo = AsyncMock(spec=WorkspaceMemberRepository)
        invite_repo = AsyncMock(spec=WorkspaceInviteRepository)

    return MockRepos()


@pytest_asyncio.fixture
async def mock_audit():
    from src.analytics.services.audit_service import AuditService
    return AsyncMock(spec=AuditService)


@pytest_asyncio.fixture
async def mock_webhooks():
    from src.webhooks.services.webhook_service import WebhookService
    return AsyncMock(spec=WebhookService)


@pytest_asyncio.fixture(autouse=True)
async def mock_mongodb():
    if os.environ.get("_USE_TESTCONTAINERS") == "1":
        yield
    else:
        from tests.mock_mongodb import _AsyncMongoClientWrapper
        with patch("src.shared.core.mongodb.AsyncIOMotorClient", _AsyncMongoClientWrapper):
            yield


@pytest_asyncio.fixture
async def mock_event_dispatcher():
    from src.shared.core.event_dispatcher import EventDispatcher
    mock = AsyncMock(spec=EventDispatcher)
    return mock
