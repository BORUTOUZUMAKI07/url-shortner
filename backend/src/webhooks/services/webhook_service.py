import base64
import hashlib
import hmac
import json

import httpx
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.errors import NotFoundError, WorkspaceNotFound
from src.webhooks.models.webhook_event import WebhookEvent
from src.webhooks.repositories.webhook_repository import WebhookRepository
from src.workspaces.repositories.workspace_repository import WorkspaceRepository


def _fernet() -> Fernet:
    from src.shared.core.config import settings
    key = base64.urlsafe_b64encode(settings.SECRET_KEY.encode()[:32].ljust(32, b'\0'))
    return Fernet(key)


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except Exception:
        return encrypted


class WebhookService:
    def __init__(self, db: AsyncSession, repo: WebhookRepository, workspace_repo: WorkspaceRepository):
        self.db = db
        self.repo = repo
        self.workspace_repo = workspace_repo

    async def _verify_access(self, workspace_id: int, user_id: int):
        ws = await self.workspace_repo.verify_access(workspace_id, user_id)
        if not ws:
            raise WorkspaceNotFound()

    async def create(self, workspace_id: int, url: str, events: list[str], secret: str, user_id: int):
        await self._verify_access(workspace_id, user_id)
        return await self.repo.create(
            workspace_id=workspace_id, url=url,
            events=",".join(events), secret=encrypt_secret(secret),
        )

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
        await self.get(webhook_id, workspace_id, user_id)
        if "events" in kwargs and isinstance(kwargs["events"], list):
            kwargs["events"] = ",".join(kwargs["events"])
        return await self.repo.update(webhook_id, **kwargs)

    async def delete(self, webhook_id: int, workspace_id: int, user_id: int):
        await self.get(webhook_id, workspace_id, user_id)
        await self.repo.delete(webhook_id)

    async def deliver_event(self, workspace_id: int, event_type: str, payload: dict):
        webhooks = await self.repo.get_active_by_event(workspace_id, event_type)
        for wh in webhooks:
            secret = decrypt_secret(wh.secret)
            payload_bytes = json.dumps(payload).encode()
            signature = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        wh.url,
                        content=payload_bytes,
                        headers={
                            "Content-Type": "application/json",
                            "X-Webhook-Signature": signature,
                            "X-Webhook-Event": event_type,
                        },
                        timeout=10.0,
                    )
                self.db.add(WebhookEvent(
                    webhook_id=wh.id, event_type=event_type,
                    payload=json.dumps(payload), status="delivered",
                    response_code=resp.status_code,
                ))
            except Exception as e:
                self.db.add(WebhookEvent(
                    webhook_id=wh.id, event_type=event_type,
                    payload=json.dumps(payload), status="failed",
                    error=str(e),
                ))
        await self.db.commit()
