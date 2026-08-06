from typing import List

from fastapi import APIRouter, Depends, status

from src.identity.models.user import User
from src.links.schemas.folder import FolderCreate, FolderResponse, FolderUpdate
from src.links.services.folder_service import FolderService
from src.shared.core.deps import get_current_user, get_folder_service

router = APIRouter(prefix="/folders", tags=["Folders"])


@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED,
    summary="Create folder")
async def create(payload: FolderCreate, current_user: User = Depends(get_current_user), svc: FolderService = Depends(get_folder_service)):
    return await svc.create(payload.name, payload.workspace_id, current_user.id)


@router.get("", response_model=List[FolderResponse],
    summary="List folders in workspace")
async def list_(workspace_id: int, current_user: User = Depends(get_current_user), svc: FolderService = Depends(get_folder_service)):
    return await svc.list(workspace_id, current_user.id)


@router.put("/{id}", response_model=FolderResponse,
    summary="Rename folder")
async def update(id: int, payload: FolderUpdate, current_user: User = Depends(get_current_user), svc: FolderService = Depends(get_folder_service)):
    return await svc.update(id, payload.name, current_user.id)


@router.delete("/{id}",
    summary="Delete folder")
async def delete(id: int, current_user: User = Depends(get_current_user), svc: FolderService = Depends(get_folder_service)):
    await svc.delete(id, current_user.id)
    return {"detail": "Folder deleted successfully."}
