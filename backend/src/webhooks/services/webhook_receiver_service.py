import hashlib
import hmac
import json
import logging

from src.shared.core.redis import redis_client
from src.shared.errors import WorkspaceNotFound
from src.webhooks.repositories.webhook_receiver_repository import WebhookReceivedEventRepository
from src.webhooks.repositories.webhook_repository import WebhookRepository
from src.webhooks.services.webhook_service import decrypt_secret
from src.workspaces.repositories.workspace_repository import WorkspaceRepository

logger = logging.getLogger("url-shortener")

_RECEIVER_RATE_LIMIT_KEY = "webhook_receiver:rate"
_RECEIVER_RATE_LIMIT = 100  # requests per minute per IP
_RECEIVER_RATE_WINDOW = 60


class WebhookReceiverService:
    def __init__(
        self,
        repo: WebhookReceivedEventRepository,
        webhook_repo: WebhookRepository,
        workspace_repo: WorkspaceRepository,
    ):
        self.repo = repo
        self.webhook_repo = webhook_repo
        self.workspace_repo = workspace_repo

    async def _check_rate_limit(self, source_ip: str | None) -> bool:
        if not source_ip:
            return True
        key = f"{_RECEIVER_RATE_LIMIT_KEY}:{source_ip}"
        try:
            current = await redis_client.incr(key)
            if current == 1:
                await redis_client.expire(key, _RECEIVER_RATE_WINDOW)
            return current <= _RECEIVER_RATE_LIMIT
        except Exception:
            return True  # fail-open if Redis is down

    async def receive(
        self, body: bytes, content_type: str,
        headers: dict[str, str], source_ip: str | None = None,
    ) -> dict:
        # Rate limit by source IP.
        if not await self._check_rate_limit(source_ip):
            return {"status": "rejected", "reason": "rate limit exceeded"}

        payload_text = body.decode()
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            payload = {"raw": payload_text}

        event_type = headers.get("x-webhook-event", "unknown")
        signature = headers.get("x-webhook-signature")

        # #6 — reject if no signature provided.
        if not signature:
            return {"status": "rejected", "reason": "missing X-Webhook-Signature header"}

        workspace_id = None
        if isinstance(payload, dict):
            workspace_id = payload.get("workspace_id")

        if not workspace_id:
            return {"status": "rejected", "reason": "no workspace_id in payload"}

        ws = await self.workspace_repo.get(workspace_id)
        if not ws:
            return {"status": "rejected", "reason": "workspace not found"}

        # #6 — verify signature against webhooks in the workspace.
        # Only accept if at least one webhook's secret matches.
        webhook_id = None
        signature_valid = False
        webhooks = await self.webhook_repo.get_workspace_webhooks(workspace_id)
        for wh in webhooks:
            if not wh.is_active:
                continue
            if not any(s.event_type == event_type for s in wh.subscriptions):
                continue
            try:
                secret = decrypt_secret(wh.secret)
                expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
                if hmac.compare_digest(signature, expected):
                    signature_valid = True
                    webhook_id = wh.id
                    break
            except Exception:
                continue

        # #6 — reject if signature is invalid (don't silently log it).
        if not signature_valid:
            logger.warning(
                "Webhook receiver: invalid signature from %s for workspace %s event %s",
                source_ip, workspace_id, event_type,
            )
            return {"status": "rejected", "reason": "invalid signature"}

        await self.repo.log_event(
            workspace_id=workspace_id, event_type=event_type,
            payload=payload_text, headers=json.dumps(dict(headers)),
            signature=signature, signature_valid=signature_valid,
            source_ip=source_ip, webhook_id=webhook_id,
        )

        return {
            "status": "received",
            "event_type": event_type,
            "signature_valid": signature_valid,
        }

    async def get_workspace_events(
        self, workspace_id: int, user_id: int,
        skip: int = 0, limit: int = 50,
    ):
        ws = await self.workspace_repo.verify_access(workspace_id, user_id)
        if not ws:
            raise WorkspaceNotFound()
        return await self.repo.get_workspace_events(workspace_id, skip=skip, limit=limit)
