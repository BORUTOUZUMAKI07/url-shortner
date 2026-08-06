from typing import List

from fastapi import APIRouter, Depends, status

from src.identity.models.user import User
from src.shared.core.deps import get_current_user, get_webhook_service
from src.webhooks.schemas.webhook import WebhookCreate, WebhookResponse, WebhookUpdate
from src.webhooks.services.webhook_service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/workspace/{workspace_id}", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED,
    summary="Create webhook",
    description="Register a new webhook endpoint for a workspace to receive real-time event notifications.")
async def create(workspace_id: int, payload: WebhookCreate, current_user: User = Depends(get_current_user), svc: WebhookService = Depends(get_webhook_service)):
    return await svc.create(workspace_id, str(payload.url), payload.events, payload.secret, current_user.id)


@router.get("/workspace/{workspace_id}", response_model=List[WebhookResponse],
    summary="List webhooks in workspace")
async def list_(workspace_id: int, current_user: User = Depends(get_current_user), svc: WebhookService = Depends(get_webhook_service)):
    return await svc.list(workspace_id, current_user.id)


@router.get("/{webhook_id}/workspace/{workspace_id}", response_model=WebhookResponse,
    summary="Get webhook details")
async def get(webhook_id: int, workspace_id: int, current_user: User = Depends(get_current_user), svc: WebhookService = Depends(get_webhook_service)):
    return await svc.get(webhook_id, workspace_id, current_user.id)


@router.put("/{webhook_id}/workspace/{workspace_id}", response_model=WebhookResponse,
    summary="Update webhook")
async def update(webhook_id: int, workspace_id: int, payload: WebhookUpdate, current_user: User = Depends(get_current_user), svc: WebhookService = Depends(get_webhook_service)):
    kwargs = {k: v for k, v in payload.model_dump().items() if v is not None}
    return await svc.update(webhook_id, workspace_id, current_user.id, **kwargs)


@router.delete("/{webhook_id}/workspace/{workspace_id}",
    summary="Delete webhook")
async def delete(webhook_id: int, workspace_id: int, current_user: User = Depends(get_current_user), svc: WebhookService = Depends(get_webhook_service)):
    await svc.delete(webhook_id, workspace_id, current_user.id)
    return {"detail": "Webhook deleted."}
