from typing import List

from fastapi import APIRouter, Depends, status

from src.identity.models.user import User
from src.links.schemas.tag import TagCreate, TagResponse
from src.links.services.tag_service import TagService
from src.shared.core.deps import get_current_user, get_tag_service

router = APIRouter(prefix="/tags", tags=["Tags"])


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED,
    summary="Create tag")
async def create(payload: TagCreate, current_user: User = Depends(get_current_user), svc: TagService = Depends(get_tag_service)):
    return await svc.create(payload.name, payload.workspace_id, current_user.id)


@router.get("", response_model=List[TagResponse],
    summary="List tags in workspace")
async def list_(workspace_id: int, current_user: User = Depends(get_current_user), svc: TagService = Depends(get_tag_service)):
    return await svc.list(workspace_id, current_user.id)


@router.delete("/{id}",
    summary="Delete tag")
async def delete(id: int, current_user: User = Depends(get_current_user), svc: TagService = Depends(get_tag_service)):
    await svc.delete(id, current_user.id)
    return {"detail": "Tag deleted successfully."}
