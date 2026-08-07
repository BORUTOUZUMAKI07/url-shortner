from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.identity.models.user import User
from src.links.models.url import URL, URLStatus
from src.shared.core.security import create_access_token, hash_password
from src.workspaces.models.workspace import Workspace
from src.workspaces.models.workspace_member import MemberRole, WorkspaceMember

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture(autouse=True)
async def mock_redis():
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None
    redis_mock.setex.return_value = True
    redis_mock.delete.return_value = True
    redis_mock.incr.return_value = 1
    redis_mock.expire.return_value = True
    redis_mock.eval.return_value = 1
    with (patch("src.shared.core.deps.redis_client", redis_mock),
          patch("src.shared.core.api_key_auth.redis_client", redis_mock),
          patch("src.identity.services.auth_service.redis_client", redis_mock)):
        yield

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





@asynccontextmanager
async def _test_lifespan(app):
    yield


@pytest_asyncio.fixture(autouse=True)
async def patch_async_session_local():
    import src.shared.core.database as db_mod

    original = db_mod.AsyncSessionLocal
    test_session = async_sessionmaker(
        bind=_get_test_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )
    db_mod.AsyncSessionLocal = test_session
    try:
        yield
    finally:
        db_mod.AsyncSessionLocal = original


@pytest_asyncio.fixture
async def db():
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
        short_code="routetest",
        original_url="https://example.com/route",
        user_id=test_user.id,
        workspace_id=test_workspace.id,
        status=URLStatus.active,
    )
    db.add(url)
    await db.flush()
    await db.refresh(url)
    return url


@pytest_asyncio.fixture(scope="session")
def app():
    # Lazy import: importing src.main at module level pulls in
    # src.shared.core.database during pytest startup, BEFORE testcontainers
    # re-creates settings — which would bind the pooled engine to the real
    # .env database. Deferring to here means database.py is imported during
    # test collection, after settings point at the container.
    from src.main import create_app
    return create_app(lifespan_override=_test_lifespan)


@pytest_asyncio.fixture
async def auth_headers(test_user: User):
    token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def client(app, db, auth_headers):
    from src.shared.core.deps import get_db
    app.dependency_overrides[get_db] = lambda: db
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as ac:
        yield ac


@pytest_asyncio.fixture
async def unauth_client(app, db):
    from src.shared.core.deps import get_db
    app.dependency_overrides[get_db] = lambda: db
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def test_member(db: AsyncSession, test_user: User, test_workspace: Workspace):
    member = WorkspaceMember(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        role=MemberRole.admin,
    )
    db.add(member)
    await db.flush()
    await db.refresh(member)
    return member
