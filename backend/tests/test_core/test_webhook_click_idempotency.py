"""Click-webhook dispatch idempotency is an atomic claim, not check-then-set.

The old code did get() -> deliver -> setex(): between the read and the write,
a concurrent consumer (or a Kafka redelivery before the offset commit lands)
also reads "absent" and both batches deliver. The rework claims the event with
setnx() before any DB work and, only on success, extends the same key into the
long completion marker — a failure releases the claim so a redelivery retries.
"""
import logging
from contextlib import contextmanager
from unittest.mock import patch

import pytest

# Register the eager model classes before anything imports the webhook consumer:
# URL.folder is a lazy string relationship ("Folder"), and if the URL mapper
# gets configured first it fails to resolve the name. In the full suite some
# unrelated earlier file happens to import these; isolated, this file must.
from src.links.models import folder as _folder  # noqa: F401
from src.links.models import tag as _tag  # noqa: F401
from src.webhooks.workers.webhook_click_consumer import deliver_click_webhooks

# Expected TTLs written here as literals, not imported from the module: the
# constants only exist in the fixed code, so importing them would make the
# unfixed version fail at collection (import error) instead of on an assertion.
PROCESS_LOCK_SECONDS = 90
DONE_TTL_SECONDS = 7 * 24 * 3600

IDKEY = "idempotency:webhook_click:e1"
LOGGER = logging.getLogger("test-webhook-click")
_EVENT = {"event_id": "e1", "workspace_id": 1, "short_code": "abc123"}


class RedisDouble:
    """Records every call so the interleaving around the DB work can be pinned.

    `get` exists so the unfixed code (read-then-write) can also run against this
    double — the assertions then fail on *behaviour* (a get where a setnx must
    happen, no claim before the DB work), not on an attribute error.
    """

    def __init__(self, shared_log):
        self.data = {}
        self.claim_ttls = {}
        self.marker_ttls = {}
        self.shared_log = shared_log

    async def setnx(self, key, ttl, value):
        self.shared_log.append(f"setnx {key}")
        if key in self.data:
            return False
        self.data[key] = value
        self.claim_ttls[key] = ttl
        return True

    async def setex(self, key, ttl, value):
        self.shared_log.append(f"setex {key}")
        self.data[key] = value
        self.marker_ttls[key] = ttl

    async def delete(self, key):
        self.shared_log.append(f"delete {key}")
        self.data.pop(key, None)

    async def get(self, key):
        self.shared_log.append(f"get {key}")
        return self.data.get(key)


class _Result:
    def scalars(self):
        return self

    def all(self):
        return []


class _Session:
    """Fake AsyncSessionLocal session: an empty workspace, commit recorded."""

    def __init__(self, shared_log, fail_execute=False):
        self.shared_log = shared_log
        self.fail_execute = fail_execute
        self.committed = False

    async def __aenter__(self):
        self.shared_log.append("db_enter")
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, *a, **k):
        self.shared_log.append("db_execute")
        if self.fail_execute:
            raise RuntimeError("db died mid-delivery")
        return _Result()

    async def commit(self):
        self.shared_log.append("db_commit")
        self.committed = True

    def add(self, *a, **k):
        pass


@contextmanager
def _patched(shared, session_factory, redis=None):
    """Keep the redis_client/AsyncSessionLocal patches active for the call."""
    redis = redis or RedisDouble(shared)
    with patch("src.webhooks.workers.webhook_click_consumer.redis_client", redis), \
         patch("src.webhooks.workers.webhook_click_consumer.AsyncSessionLocal", session_factory):
        yield redis


async def test_success_claims_first_and_marks_after_commit():
    """setnx before any DB work; the done-marker only after the commit — the
    crash-correct order. The unfixed code logged `get ... db_enter db_commit
    setex ...`, so the leading `setnx` assertion fails there."""
    shared = []
    with _patched(shared, lambda: _Session(shared)) as redis:
        await deliver_click_webhooks(_EVENT, LOGGER)

    assert shared == ["setnx idempotency:webhook_click:e1", "db_enter",
                      "db_execute", "db_commit", "setex idempotency:webhook_click:e1"], (
        f"claim must precede the DB work and the marker must follow the commit; got {shared}"
    )
    assert redis.claim_ttls.get(IDKEY) == PROCESS_LOCK_SECONDS
    assert redis.marker_ttls.get(IDKEY) == DONE_TTL_SECONDS


async def test_already_claimed_event_is_skipped_without_touching_the_db():
    shared = []
    redis = RedisDouble(shared)
    redis.data[IDKEY] = "claimed-by-other-consumer"

    def explode(*a, **k):
        raise AssertionError("an already-claimed event must not open a DB session")

    with _patched(shared, explode, redis=redis):
        await deliver_click_webhooks(_EVENT, LOGGER)

    assert shared == ["setnx idempotency:webhook_click:e1"]
    assert redis.claim_ttls.get(IDKEY) is None, "a loser must not overwrite the claim"


async def test_failure_releases_the_claim_so_a_redelivery_can_retry():
    shared = []
    with _patched(shared, lambda: _Session(shared, fail_execute=True)) as redis:
        with pytest.raises(RuntimeError):
            await deliver_click_webhooks(_EVENT, LOGGER)

    assert "delete idempotency:webhook_click:e1" in shared
    assert IDKEY not in redis.data, "the claim must not linger after a failed delivery"


async def test_no_event_id_dispatches_without_idempotency_round_trips():
    shared = []
    with _patched(shared, lambda: _Session(shared)) as redis:
        await deliver_click_webhooks({"workspace_id": 1}, LOGGER)

    assert shared == ["db_enter", "db_execute", "db_commit"], (
        f"events without an id must not touch the idempotency key; got {shared}"
    )
    assert not redis.data
