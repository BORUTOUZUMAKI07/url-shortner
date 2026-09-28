import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time

from cryptography.fernet import Fernet

from src.shared.core.safe_url import is_safe_url, safe_post
from src.shared.errors import BadRequestError, NotFoundError, RoleTooLow, WorkspaceNotFound
from src.webhooks.models.webhook import Webhook
from src.webhooks.models.webhook_event import WebhookEvent
from src.webhooks.repositories.webhook_repository import WebhookRepository
from src.workspaces.models.workspace_member import MemberRole
from src.workspaces.repositories.workspace_repository import WorkspaceRepository

logger = logging.getLogger("url-shortener")


# ---------------------------------------------------------------------------
# Encryption — dedicated key, not the JWT SECRET_KEY (#7)
# ---------------------------------------------------------------------------
def _fernet() -> Fernet:
    from src.shared.core.config import settings
    raw = settings.WEBHOOK_SECRET_KEY.encode()
    return Fernet(base64.urlsafe_b64encode(raw[:32].ljust(32, b"\0")))


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except Exception:
        return encrypted


# ---------------------------------------------------------------------------
# Concurrency semaphore (#1 — bounding background delivery parallelism)
# ---------------------------------------------------------------------------
_delivery_semaphore = asyncio.Semaphore(10)


# ---------------------------------------------------------------------------
# Per-endpoint circuit breaker (#8)
# ---------------------------------------------------------------------------
_CONSECUTIVE_FAILURES: dict[int, tuple[int, float]] = {}
_CIRCUIT_OPEN_UNTIL: dict[int, float] = {}
_MAX_CONSECUTIVE_FAILURES = 5
_CIRCUIT_OPEN_SECONDS = 300  # 5 minutes
# A failure older than this is not "consecutive" any more. Without a time bound
# the counter is only ever cleared by a success or by the circuit opening, so a
# webhook that fails once or twice and then goes quiet keeps its entry — and its
# id — for the life of the process. Bounding it in time is also the more honest
# reading of "consecutive": three failures spread over a day are not a streak.
_FAILURE_WINDOW_SECONDS = 300  # 5 minutes

# Strong references to in-flight fire-and-forget deliveries, so the event loop
# cannot garbage-collect a task that has already suspended on its HTTP POST.
# Without this a delivery can be destroyed mid-flight: the caller awaited
# nothing, gets its 200, and the event is silently lost. Mirrors _track() in
# shared/events/kafka.py, for the same reason.
_pending_deliveries: set[asyncio.Task] = set()


def _track(task: asyncio.Task) -> None:
    _pending_deliveries.add(task)
    task.add_done_callback(_pending_deliveries.discard)


def _is_circuit_open(webhook_id: int) -> bool:
    open_until = _CIRCUIT_OPEN_UNTIL.get(webhook_id)
    if open_until is None:
        return False
    if time.time() >= open_until:
        _CIRCUIT_OPEN_UNTIL.pop(webhook_id, None)
        _CONSECUTIVE_FAILURES.pop(webhook_id, None)
        return False
    return True


def _record_delivery_success(webhook_id: int) -> None:
    _forget_webhook(webhook_id)


def _record_delivery_failure(webhook_id: int) -> None:
    now = time.time()
    count, last_at = _CONSECUTIVE_FAILURES.get(webhook_id, (0, 0.0))
    if now - last_at > _FAILURE_WINDOW_SECONDS:
        count = 0  # the streak went stale; start a new one
    count += 1
    _CONSECUTIVE_FAILURES[webhook_id] = (count, now)
    if count >= _MAX_CONSECUTIVE_FAILURES:
        _CIRCUIT_OPEN_UNTIL[webhook_id] = now + _CIRCUIT_OPEN_SECONDS


def _forget_webhook(webhook_id: int) -> None:
    """Drop all breaker state for a webhook that no longer exists."""
    _CONSECUTIVE_FAILURES.pop(webhook_id, None)
    _CIRCUIT_OPEN_UNTIL.pop(webhook_id, None)


# ---------------------------------------------------------------------------
# Shared delivery function — single implementation (#2)
# ---------------------------------------------------------------------------
async def deliver_single_webhook(
    webhook_id: int,
    url: str,
    secret_encrypted: str,
    payload: dict,
    event_type: str,
) -> tuple[bool, int | None, str | None]:
    """Deliver a single webhook with HMAC signing, DNS-pinned.

    Returns (success, response_code, error).
    """
    if _is_circuit_open(webhook_id):
        logger.warning("Circuit breaker open for webhook %s (%s), skipping delivery", webhook_id, url)
        return False, None, "Circuit breaker open"

    secret = decrypt_secret(secret_encrypted)
    payload_bytes = json.dumps(payload).encode()
    signature = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

    try:
        async with _delivery_semaphore:
            resp = await safe_post(
                url,
                content=payload_bytes,
                timeout=10.0,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature,
                    "X-Webhook-Event": event_type,
                },
            )
        if resp is None:
            _record_delivery_failure(webhook_id)
            return False, None, "Unsafe or unreachable webhook URL"
        if resp.is_success:
            _record_delivery_success(webhook_id)
            return True, resp.status_code, None
        else:
            _record_delivery_failure(webhook_id)
            error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            return False, resp.status_code, error
    except Exception as e:
        _record_delivery_failure(webhook_id)
        return False, None, str(e)


# ---------------------------------------------------------------------------
# Background delivery task (#1, #5 — off request path, DLQ-consistent)
# ---------------------------------------------------------------------------
async def _deliver_event_background(
    workspace_id: int,
    event_type: str,
    payload: dict,
) -> None:
    """Background task: look up webhooks, deliver, record results."""
    from src.shared.core.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            repo = WebhookRepository(db)
            webhooks = await repo.get_active_by_event(workspace_id, event_type)
            if not webhooks:
                return

            for wh in webhooks:
                success, code, error = await deliver_single_webhook(
                    wh.id, wh.url, wh.secret, payload, event_type,
                )
                status = "delivered" if success else "failed"
                db.add(WebhookEvent(
                    webhook_id=wh.id,
                    event_type=event_type,
                    payload=json.dumps(payload),
                    status=status,
                    response_code=code,
                    error=error,
                ))

            await db.commit()
    except Exception as e:
        logger.warning("Background webhook delivery failed (workspace=%s, event=%s): %s",
                        workspace_id, event_type, e)


# ---------------------------------------------------------------------------
# WebhookService
# ---------------------------------------------------------------------------
class WebhookService:
    def __init__(self, repo: WebhookRepository, workspace_repo: WorkspaceRepository):
        self.repo = repo
        self.workspace_repo = workspace_repo

    async def _verify_access(self, workspace_id: int, user_id: int):
        ws = await self.workspace_repo.verify_access(workspace_id, user_id)
        if not ws:
            raise WorkspaceNotFound()

    async def _verify_write_role(self, workspace_id: int, user_id: int):
        if not await self.workspace_repo.verify_role(workspace_id, user_id, MemberRole.editor):
            raise RoleTooLow("editor")

    async def _verify_safe_webhook_url(self, url: str):
        if not await is_safe_url(url):
            raise BadRequestError("Webhook URL must be http(s) and resolve to a public address")

    async def create(self, workspace_id: int, url: str, events: list[str], secret: str, user_id: int):
        await self._verify_access(workspace_id, user_id)
        await self._verify_write_role(workspace_id, user_id)
        await self._verify_safe_webhook_url(url)
        webhook = Webhook(workspace_id=workspace_id, url=str(url), secret=encrypt_secret(secret))
        return await self.repo.create_with_subscriptions(webhook, events)

    async def list(self, workspace_id: int, user_id: int):
        await self._verify_access(workspace_id, user_id)
        return await self.repo.get_workspace_webhooks(workspace_id)

    async def get(self, webhook_id: int, workspace_id: int, user_id: int):
        await self._verify_access(workspace_id, user_id)
        wh = await self.repo.get(webhook_id)
        if not wh or wh.workspace_id != workspace_id:
            raise NotFoundError("Webhook not found.")
        return wh

    async def update(self, webhook_id: int, workspace_id: int, user_id: int, **kwargs):
        wh = await self.get(webhook_id, workspace_id, user_id)
        await self._verify_write_role(workspace_id, user_id)
        events = kwargs.pop("events", None)
        if events is not None:
            events = [str(e) for e in events]
        if "url" in kwargs:
            url = str(kwargs["url"])
            await self._verify_safe_webhook_url(url)
            kwargs["url"] = url
        if "secret" in kwargs and kwargs["secret"]:
            kwargs["secret"] = encrypt_secret(kwargs["secret"])
        if kwargs:
            await self.repo.update(webhook_id, **kwargs)
        if events is not None:
            await self.repo.sync_subscriptions(wh, events)
        return await self.repo.get(webhook_id)

    async def delete(self, webhook_id: int, workspace_id: int, user_id: int):
        await self.get(webhook_id, workspace_id, user_id)
        await self._verify_write_role(workspace_id, user_id)
        await self.repo.delete(webhook_id)
        # The breaker keys are module-level and outlive the row, so a deleted
        # webhook would otherwise leave its counter behind forever.
        _forget_webhook(webhook_id)

    # #1 — fire-and-forget: returns immediately, delivery runs in background.
    # #5 — background task records delivery status (delivered/failed) per
    #      webhook so the retry worker can pick up failures — identical
    #      semantics to the click consumer and retry worker.
    async def deliver_event(self, workspace_id: int, event_type: str, payload: dict) -> None:
        # The Task needs a strong reference for its whole life. The event loop
        # only holds one through the ready queue, so once the coroutine first
        # suspends — which here is its outbound HTTP POST, i.e. almost
        # immediately — a bare create_task() result is collectable and the
        # delivery can be destroyed without ever finishing. The caller awaits
        # nothing, so the event just disappears. Same fix, and the same reason,
        # as _track() in shared/events/kafka.py.
        _track(asyncio.create_task(_deliver_event_background(workspace_id, event_type, payload)))
