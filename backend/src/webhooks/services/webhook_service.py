import base64
import hashlib
import hmac
import json

import httpx
from cryptography.fernet import Fernet

from src.shared.errors import NotFoundError, RoleTooLow, WorkspaceNotFound
from src.webhooks.models.webhook import Webhook
from src.webhooks.repositories.webhook_repository import WebhookRepository
from src.workspaces.models.workspace_member import MemberRole
from src.workspaces.repositories.workspace_repository import WorkspaceRepository


def _fernet() -> Fernet:
    from src.shared.core.config import settings
    key = base64.urlsafe_b64encode(settings.SECRET_KEY.encode()[:32].ljust(32, b'\0'))
    return Fernet(key)


# Shared AsyncClient — creating one per webhook delivery wastes a connection
# pool per delivery. AsyncClient is designed to be reused across requests.
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=10.0)
    return _client


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except Exception:
        return encrypted


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

    async def create(self, workspace_id: int, url: str, events: list[str], secret: str, user_id: int):
        await self._verify_access(workspace_id, user_id)
        await self._verify_write_role(workspace_id, user_id)
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
            kwargs["url"] = str(kwargs["url"])
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

    async def deliver_event(self, workspace_id: int, event_type: str, payload: dict):
        webhooks = await self.repo.get_active_by_event(workspace_id, event_type)
        for wh in webhooks:
            secret = decrypt_secret(wh.secret)
            payload_bytes = json.dumps(payload).encode()
            signature = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
            try:
                resp = await _get_client().post(
                    wh.url,
                    content=payload_bytes,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Signature": signature,
                        "X-Webhook-Event": event_type,
                    },
                    timeout=10.0,
                )
                if resp.is_success:
                    await self.repo.record_delivery(
                        wh.id, event_type, json.dumps(payload), "delivered",
                        response_code=resp.status_code,
                    )
                else:
                    await self.repo.record_delivery(
                        wh.id, event_type, json.dumps(payload), "failed",
                        response_code=resp.status_code,
                        error=f"HTTP {resp.status_code}: {resp.text[:200]}",
                    )
            except Exception as e:
                await self.repo.record_delivery(
                    wh.id, event_type, json.dumps(payload), "failed", error=str(e),
                )
