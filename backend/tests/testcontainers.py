"""Docker container lifecycle for testcontainers-based integration testing."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

_pg = None
_mongo = None
_redis = None

# Every env var start_containers() touches. Snapshotted before the work begins
# so a failed start can put them back rather than leaving the process pointed at
# containers that are no longer running.
_MANAGED_ENV = (
    "DATABASE_URL", "MONGODB_URI", "REDIS_URL", "ENVIRONMENT", "_USE_TESTCONTAINERS",
    "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN",
)


def start_containers() -> None:
    """Start Postgres/Mongo/Redis, migrate, and wire the resulting env.

    Atomic by contract: on failure nothing is published. The module globals and
    the env vars are only updated once all three containers are up and the
    migration has succeeded, so a failed start leaves whatever state the caller
    already had completely untouched.

    The rollback lives in here because neither caller has a cleanup path for a
    *failed* start:
      * tests/conftest.py pytest_sessionfinish() only calls stop_containers()
        when _USE_TESTCONTAINERS == "1", and that flag is set on the last line
        of a successful start — so a failed `alembic upgrade head` skipped
        teardown entirely and stranded a live Postgres container.
      * scripts/e2e_server.py calls start_containers() before its try/finally
        block exists, so an exception there skipped the finally too.
    Only Testcontainers' Ryuk reaper collected those, some time later.

    Containers are tracked in locals and cleaned up by identity, never via the
    globals. Assigning the globals as each container came up would make a
    mid-sequence failure stop whatever the *previous* successful call owned —
    which, when start_containers() is re-entered inside a live session, is the
    very database the rest of the suite is using.
    """
    from testcontainers.mongodb import MongoDbContainer  # type: ignore[import-untyped]
    from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]
    from testcontainers.redis import RedisContainer  # type: ignore[import-untyped]

    import src.shared.core.config

    prior_env = {key: os.environ.get(key) for key in _MANAGED_ENV}
    prior_settings = src.shared.core.config.settings

    pg = None
    mongo = None
    redis_container = None
    try:
        pg = PostgresContainer("postgres:16")
        pg.start()
        sync_url = pg.get_connection_url()
        async_url = (
            sync_url
            .replace("postgresql+psycopg2://", "postgresql+asyncpg://")
            .replace("postgresql://", "postgresql+asyncpg://")
        )
        os.environ["DATABASE_URL"] = async_url
        # These runs are definitionally not production. ENVIRONMENT defaults to
        # "production", which is exactly the mode that refuses to boot without a
        # real SECRET_KEY — so say so explicitly instead of inheriting the default.
        os.environ.setdefault("ENVIRONMENT", "test")

        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(BACKEND_DIR),
            env={**os.environ, "DATABASE_URL": async_url},
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Alembic migration failed:\n{result.stdout}\n{result.stderr}")

        mongo = MongoDbContainer("mongo:7")
        mongo.start()
        os.environ["MONGODB_URI"] = mongo.get_connection_url()

        redis_container = RedisContainer("redis:7")
        redis_container.start()
        os.environ["REDIS_URL"] = f"redis://localhost:{redis_container.get_exposed_port(6379)}"

        # Never let the test process reach the real production Upstash cache.
        # `_build_redis_client` prefers the Upstash REST client whenever BOTH
        # credentials are set — and `backend/.env` ships them — so without this
        # every route test evaluated rate limits / idempotency markers against
        # the production cache: one run's consumed `verify_email_resend` budget
        # (5 per 5 min) 429'd the next run's identical tests, and the write
        # itself leaked test state into production. Blank the vars ("" has
        # pydantic-settings env precedence over the .env copies) so the Settings
        # rebuild below reads falsy values and the first `import redis` builds
        # the plain-Redis adapter against the container above.
        os.environ["UPSTASH_REDIS_REST_URL"] = ""
        os.environ["UPSTASH_REDIS_REST_TOKEN"] = ""

        os.environ["_USE_TESTCONTAINERS"] = "1"

        # Rebuild Settings() only AFTER every *_URI/_URL env var is set. Otherwise
        # pydantic-settings keeps the defaults (e.g. mongodb://localhost:27017) and
        # tests connect to nothing — or, worse, to a stray local service — instead
        # of the containers. On CI runners this made every init_mongodb() test fail
        # with "localhost:27017: Connection refused".
        src.shared.core.config.settings = src.shared.core.config.Settings()
    except BaseException:
        # Stop only what THIS call started, newest first. A container that was
        # constructed but never started is safe to stop() — testcontainers treats
        # that as a no-op.
        for container in (redis_container, mongo, pg):
            if container is not None:
                try:
                    container.stop()
                except Exception:  # noqa: BLE001 - never mask the original error
                    pass
        for key, value in prior_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        src.shared.core.config.settings = prior_settings
        raise
    else:
        # Published only once everything above succeeded.
        _pg, _mongo, _redis = pg, mongo, redis_container


def stop_containers() -> None:
    global _pg, _mongo, _redis
    for container in (_redis, _mongo, _pg):
        if container is not None:
            try:
                container.stop()
            except Exception:
                pass
    _pg = _mongo = _redis = None
