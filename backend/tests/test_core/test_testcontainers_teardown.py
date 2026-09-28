"""start_containers() must not strand a live container when a step fails.

Both callers of start_containers() have no cleanup path for a *failed* start:

  * tests/conftest.py pytest_sessionfinish() only calls stop_containers() when
    _USE_TESTCONTAINERS == "1", and that flag is only set on the last line of a
    successful start — so a failed `alembic upgrade head` skipped teardown.
  * scripts/e2e_server.py calls start_containers() before its try/finally block
    exists, so an exception there skipped the finally.

So the rollback lives inside start_containers() itself, and these tests pin it.
They drive it with fakes and never touch Docker.
"""
from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator

import pytest

from tests import testcontainers as tc


class _FakeContainer:
    """Stand-in for a testcontainers container that records start/stop calls."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1

    def get_connection_url(self) -> str:
        return "postgresql://u:p@localhost:5432/db"

    def get_exposed_port(self, port: int) -> int:
        return port


# Spelled out here rather than read from tests.testcontainers, so these tests do
# not depend on the fix existing: run against the unfixed module they must fail
# on the stranded-container assertion, not error out on a missing attribute.
_MANAGED_ENV = ("DATABASE_URL", "MONGODB_URI", "REDIS_URL", "ENVIRONMENT", "_USE_TESTCONTAINERS")


def _ok(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")


def _alembic_fails(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=1, stdout="partial", stderr="boom")


@pytest.fixture(autouse=True)
def _isolate_global_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Make calling start_containers() for real safe inside a test session.

    Under --use-testcontainers the module globals hold the live containers the
    entire suite depends on, and the env vars point at them. These tests
    reassign both, so snapshot and restore or the session loses its teardown and
    its database.
    """
    saved_containers = (tc._pg, tc._mongo, tc._redis)
    saved_env = {key: os.environ.get(key) for key in _MANAGED_ENV}
    import src.shared.core.config as cfg

    monkeypatch.setattr(cfg, "settings", cfg.settings)
    try:
        yield
    finally:
        tc._pg, tc._mongo, tc._redis = saved_containers
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_alembic_failure_stops_postgres_and_restores_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """The regression: alembic is the first thing that can fail, after PG is up."""
    fake_pg = _FakeContainer()
    monkeypatch.setattr("testcontainers.postgres.PostgresContainer", lambda *a, **k: fake_pg)
    monkeypatch.setenv("DATABASE_URL", "postgresql://sentinel:kept@host/db")
    monkeypatch.setattr(tc.subprocess, "run", _alembic_fails)

    with pytest.raises(RuntimeError, match="Alembic migration failed"):
        tc.start_containers()

    assert fake_pg.started == 1
    assert fake_pg.stopped == 1, "a live Postgres container was stranded"
    assert os.environ["DATABASE_URL"] == "postgresql://sentinel:kept@host/db"
    # delenv first: under --use-testcontainers this flag is legitimately set for
    # the whole session, so "absent" is only true because we made it so.
    monkeypatch.delenv("_USE_TESTCONTAINERS", raising=False)
    assert "_USE_TESTCONTAINERS" not in os.environ
    assert tc._pg is None


def test_failed_start_leaves_containers_owned_by_a_previous_call_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A re-entrant start must not stop the live session's own containers.

    Regression: the first version of the rollback called stop_containers(), which
    reads the module globals. Those globals are assigned one container at a time,
    so on an alembic failure _pg held this call's new container while _mongo and
    _redis still held the *previous* call's live ones — and the rollback stopped
    them. Inside a --use-testcontainers session that killed the running Mongo,
    which is why every test_workers mongo test started failing with
    ServerSelectionTimeoutError. Cleanup must be by identity, not via globals.
    """
    live_pg, live_mongo, live_redis = _FakeContainer(), _FakeContainer(), _FakeContainer()
    for fake in (live_pg, live_mongo, live_redis):
        fake.start()
    tc._pg, tc._mongo, tc._redis = live_pg, live_mongo, live_redis

    new_pg = _FakeContainer()
    monkeypatch.setattr("testcontainers.postgres.PostgresContainer", lambda *a, **k: new_pg)
    monkeypatch.setattr(tc.subprocess, "run", _alembic_fails)

    with pytest.raises(RuntimeError, match="Alembic migration failed"):
        tc.start_containers()

    assert new_pg.stopped == 1, "the container this call started was not cleaned up"
    for name, fake in (("postgres", live_pg), ("mongo", live_mongo), ("redis", live_redis)):
        assert fake.stopped == 0, f"rollback stopped the live session's {name} container"
    assert (tc._pg, tc._mongo, tc._redis) == (live_pg, live_mongo, live_redis)


def test_later_failure_stops_everything_started_so_far(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failure after mongo starts must unwind postgres too, not just mongo."""
    fake_pg, fake_mongo = _FakeContainer(), _FakeContainer()
    monkeypatch.setattr("testcontainers.postgres.PostgresContainer", lambda *a, **k: fake_pg)
    monkeypatch.setattr("testcontainers.mongodb.MongoDbContainer", lambda *a, **k: fake_mongo)
    monkeypatch.setattr(tc.subprocess, "run", _ok)

    def _mongo_will_not_start() -> None:
        raise RuntimeError("mongo refused to start")

    fake_mongo.start = _mongo_will_not_start  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="mongo refused to start"):
        tc.start_containers()

    assert fake_pg.stopped == 1, "postgres was not unwound when a later step failed"
    assert fake_mongo.stopped == 1
    assert tc._pg is None and tc._mongo is None and tc._redis is None


def test_failure_restores_a_preexisting_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env is restored to its prior value, not merely cleared."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://real:container@host:5432/db")
    monkeypatch.setenv("_USE_TESTCONTAINERS", "1")
    monkeypatch.setattr("testcontainers.postgres.PostgresContainer", lambda *a, **k: _FakeContainer())
    monkeypatch.setattr(tc.subprocess, "run", _alembic_fails)

    with pytest.raises(RuntimeError, match="Alembic migration failed"):
        tc.start_containers()

    assert os.environ["DATABASE_URL"] == "postgresql://real:container@host:5432/db"
    assert os.environ["_USE_TESTCONTAINERS"] == "1"


def test_successful_start_does_not_roll_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard the happy path: the fix must not stop containers that came up fine."""
    fake_pg, fake_mongo, fake_redis = _FakeContainer(), _FakeContainer(), _FakeContainer()
    monkeypatch.setattr("testcontainers.postgres.PostgresContainer", lambda *a, **k: fake_pg)
    monkeypatch.setattr("testcontainers.mongodb.MongoDbContainer", lambda *a, **k: fake_mongo)
    monkeypatch.setattr("testcontainers.redis.RedisContainer", lambda *a, **k: fake_redis)
    monkeypatch.setattr(tc.subprocess, "run", _ok)
    monkeypatch.delenv("_USE_TESTCONTAINERS", raising=False)

    try:
        tc.start_containers()

        assert fake_pg.stopped == 0 and fake_mongo.stopped == 0 and fake_redis.stopped == 0
        assert os.environ["_USE_TESTCONTAINERS"] == "1"
        assert os.environ["DATABASE_URL"].startswith("postgresql+asyncpg://")
        assert os.environ["MONGODB_URI"]
        assert os.environ["REDIS_URL"].startswith("redis://localhost:")
    finally:
        tc.stop_containers()
