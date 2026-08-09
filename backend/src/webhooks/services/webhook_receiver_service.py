import hashlib
import hmac
import json

from src.shared.errors import WorkspaceNotFound
from src.webhooks.repositories.webhook_receiver_repository import WebhookReceivedEventRepository
from src.webhooks.repositories.webhook_repository import WebhookRepository
from src.webhooks.services.webhook_service import decrypt_secret
from src.workspaces.repositories.workspace_repository import WorkspaceRepository


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

    async def receive(
        self, body: bytes, content_type: str,
        headers: dict[str, str], source_ip: str | None = None,
    ) -> dict:
        payload_text = body.decode()
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            payload = {"raw": payload_text}

        event_type = headers.get("x-webhook-event", "unknown")
        signature = headers.get("x-webhook-signature")

        workspace_id = None
        if isinstance(payload, dict):
            workspace_id = payload.get("workspace_id")

        if not workspace_id:
            return {"status": "ignored", "reason": "no workspace_id in payload"}

        ws = await self.workspace_repo.get(workspace_id)
        if not ws:
            return {"status": "ignored", "reason": "workspace not found"}

        webhook_id = None
        signature_valid = False
        if signature:
            webhooks = await self.webhook_repo.get_workspace_webhooks(workspace_id)
            for wh in webhooks:
                if any(s.event_type == event_type for s in wh.subscriptions):
                    secret = decrypt_secret(wh.secret)
                    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
                    if hmac.compare_digest(signature, expected):
                        signature_valid = True
                        webhook_id = wh.id
                        break

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
