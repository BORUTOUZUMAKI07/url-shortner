from typing import List

from fastapi import APIRouter, Depends, Query, Request

from src.identity.models.user import User
from src.shared.core.deps import get_current_user, get_webhook_receiver_service
from src.webhooks.schemas.webhook_receiver import WebhookReceivedEventResponse
from src.webhooks.services.webhook_receiver_service import WebhookReceiverService

router = APIRouter(tags=["Webhook Receiver"])


@router.post("/webhook-receiver",
    summary="Receive webhook event",
    description="Public endpoint that receives webhook POST deliveries. Verifies HMAC signature and stores the event for viewing.")
async def receive_webhook(
    request: Request,
    svc: WebhookReceiverService = Depends(get_webhook_receiver_service),
):
    body = await request.body()
    headers = dict(request.headers)
    source_ip = request.client.host if request.client else None
    return await svc.receive(body, request.headers.get("content-type", ""), headers, source_ip)


@router.get("/webhook-receiver/events/{workspace_id}", response_model=List[WebhookReceivedEventResponse],
    summary="List received webhook events")
async def list_received_events(
    workspace_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    svc: WebhookReceiverService = Depends(get_webhook_receiver_service),
):
    return await svc.get_workspace_events(workspace_id, current_user.id, skip=skip, limit=limit)
