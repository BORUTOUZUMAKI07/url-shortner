from typing import List

from fastapi import APIRouter, Depends, status

from src.identity.models.user import User
from src.identity.schemas.api_key import (
    APIKeyAggregateQuota,
    APIKeyCreate,
    APIKeyCreateResponse,
    APIKeyResponse,
)
from src.identity.services.api_key_service import APIKeyService
from src.shared.core.deps import get_api_key_service, get_current_user

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.post("", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED,
    summary="Create API key",
    description="Creates a new API key. The full key is returned only once in the response.")
async def create(payload: APIKeyCreate, current_user: User = Depends(get_current_user), svc: APIKeyService = Depends(get_api_key_service)):
    api_key, raw_key = await svc.create(payload.name, current_user.id, payload.expires_at)
    return APIKeyCreateResponse(
        id=api_key.id, name=api_key.name, prefix=api_key.prefix,
        status=api_key.status, expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at, created_at=api_key.created_at,
        key=raw_key,
    )


@router.get("", response_model=List[APIKeyResponse],
    summary="List API keys")
async def list_(current_user: User = Depends(get_current_user), svc: APIKeyService = Depends(get_api_key_service)):
    return await svc.list(current_user.id)


@router.get("/quota-summary", response_model=APIKeyAggregateQuota,
    summary="Aggregate API key quota usage",
    description="Per-user daily quota usage summed across the user's active API keys in a single call.")
async def get_quota_summary(current_user: User = Depends(get_current_user), svc: APIKeyService = Depends(get_api_key_service)):
    return await svc.get_aggregate_quota(current_user.id)


@router.delete("/{id}",
    summary="Revoke API key")
async def revoke(id: int, current_user: User = Depends(get_current_user), svc: APIKeyService = Depends(get_api_key_service)):
    await svc.revoke(id, current_user.id)
    return {"detail": "API key revoked successfully."}


@router.post("/{id}/rotate", response_model=APIKeyCreateResponse,
    summary="Rotate API key",
    description="Revokes the existing key and issues a new one with the same name.")
async def rotate(id: int, current_user: User = Depends(get_current_user), svc: APIKeyService = Depends(get_api_key_service)):
    new_key, raw_key = await svc.rotate(id, current_user.id)
    return APIKeyCreateResponse(
        id=new_key.id, name=new_key.name, prefix=new_key.prefix,
        status=new_key.status, expires_at=new_key.expires_at,
        last_used_at=new_key.last_used_at, created_at=new_key.created_at,
        key=raw_key,
    )


@router.get("/{id}/quota",
    summary="Get API key quota usage")
async def get_quota(id: int, current_user: User = Depends(get_current_user), svc: APIKeyService = Depends(get_api_key_service)):
    return await svc.get_quota(id, current_user.id)
