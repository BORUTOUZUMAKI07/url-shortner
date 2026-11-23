import contextlib
import os
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


class _FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str):
        self.store[key] = value
        self.ttls[key] = ttl
        return True

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
        if nx and key in self.store:
            return None
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True

    async def delete(self, *keys: str):
        count = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                count += 1
            if k in self.sets:
                del self.sets[k]
                count += 1
        return count

    async def incr(self, key: str):
        val = int(self.store.get(key, "0")) + 1
        self.store[key] = str(val)
        return val

    async def expire(self, key: str, ttl: int):
        self.ttls[key] = ttl
        return True

    async def sadd(self, key: str, *values: str):
        s = self.sets.setdefault(key, set())
        before = len(s)
        for v in values:
            s.add(v)
        return len(s) - before

    async def srem(self, key: str, *values: str):
        s = self.sets.get(key, set())
        count = 0
        for v in values:
            if v in s:
                s.remove(v)
                count += 1
        return count

    async def smembers(self, key: str):
        return set(self.sets.get(key, set()))

    async def eval(self, script: str, numkeys: int, *keys_and_args):
        # Default: return 1 (success) for Lua scripts like refresh rotation.
        # Tests needing specific behavior should override this attribute.
        return 1

    async def getdel(self, key: str):
        val = self.store.pop(key, None)
        return val

    async def scan(self, cursor=0, match=None, count=None):
        # Minimal scan implementation for tests.
        import fnmatch
        keys = list(self.store.keys()) + list(self.sets.keys())
        if match:
            keys = [k for k in keys if fnmatch.fnmatch(k, match)]
        return 0, keys

    async def mget(self, *keys: str):
        return [self.store.get(k) for k in keys]

    async def ping(self):
        return True

    def pipeline(self):
        return self

    async def execute(self):
        return []

    async def aclose(self):
        return None


@pytest_asyncio.fixture(autouse=True)
async def mock_redis():
    from src.shared.core.redis import RateLimitResult

    async def _allow_rate_limit(key: str, capacity: int, refill_rate_per_sec: float) -> RateLimitResult:
        return RateLimitResult(limited=False, remaining=capacity, retry_after_seconds=None, reset_after_seconds=0.0)

    redis_mock = _FakeRedis()
    patches = [
        patch("src.shared.core.deps.redis_client", redis_mock),
        patch("src.shared.core.api_key_auth.redis_client", redis_mock),
        patch("src.identity.services.auth_service.redis_client", redis_mock),
        patch("src.identity.services.profile_service.redis_client", redis_mock),
        patch("src.identity.services.session_revocation.redis_client", redis_mock),
        patch("src.identity.routes.auth.check_rate_limit", _allow_rate_limit),
    ]
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        yield redis_mock

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
    if os.environ.get("_USE_TESTCONTAINERS") != "1":
        pytest.fail(
            "DB-backed route tests require --use-testcontainers (Docker). "
            "Refusing to connect to the real .env database. Never run the route suite without it."
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
