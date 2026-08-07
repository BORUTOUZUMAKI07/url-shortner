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


def start_containers() -> None:
    from testcontainers.mongodb import MongoDbContainer  # type: ignore[import-untyped]
    from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]
    from testcontainers.redis import RedisContainer  # type: ignore[import-untyped]

    global _pg, _mongo, _redis

    _pg = PostgresContainer("postgres:16")
    _pg.start()
    sync_url = _pg.get_connection_url()
    async_url = (
        sync_url
        .replace("postgresql+psycopg2://", "postgresql+asyncpg://")
        .replace("postgresql://", "postgresql+asyncpg://")
    )
    os.environ["DATABASE_URL"] = async_url

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND_DIR),
        env={**os.environ, "DATABASE_URL": async_url},
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Alembic migration failed:\n{result.stdout}\n{result.stderr}")

    import src.shared.core.config
    src.shared.core.config.settings = src.shared.core.config.Settings()

    _mongo = MongoDbContainer("mongo:7")
    _mongo.start()
    os.environ["MONGODB_URI"] = _mongo.get_connection_url()

    _redis = RedisContainer("redis:7")
    _redis.start()
    os.environ["REDIS_URL"] = f"redis://localhost:{_redis.get_exposed_port(6379)}"

    os.environ["_USE_TESTCONTAINERS"] = "1"


def stop_containers() -> None:
    global _pg, _mongo, _redis
    for container in (_redis, _mongo, _pg):
        if container is not None:
            try:
                container.stop()
            except Exception:
                pass
    _pg = _mongo = _redis = None
