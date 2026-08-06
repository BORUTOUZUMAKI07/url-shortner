from typing import List

from fastapi import APIRouter, Depends, status

from src.identity.models.user import User
from src.shared.core.deps import get_current_user, get_workspace_service
from src.workspaces.schemas.workspace import WorkspaceCreate, WorkspaceResponse
from src.workspaces.schemas.workspace_invite import AcceptInviteRequest, InviteCreate, InviteResponse
from src.workspaces.schemas.workspace_member import MemberResponse, UpdateMemberRole
from src.workspaces.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED,
    summary="Create workspace")
async def create(payload: WorkspaceCreate, current_user: User = Depends(get_current_user), svc: WorkspaceService = Depends(get_workspace_service)):
    return await svc.create(payload.name, current_user.id)


@router.get("", response_model=List[WorkspaceResponse],
    summary="List workspaces",
    description="Returns all workspaces the current user owns or is a member of.")
async def list_(current_user: User = Depends(get_current_user), svc: WorkspaceService = Depends(get_workspace_service)):
    return await svc.list(current_user.id)


@router.get("/{id}", response_model=WorkspaceResponse,
    summary="Get workspace details")
async def get(id: int, current_user: User = Depends(get_current_user), svc: WorkspaceService = Depends(get_workspace_service)):
    return await svc.get(id, current_user.id)


@router.put("/{id}", summary="Rename workspace")
async def rename(id: int, payload: WorkspaceCreate, current_user: User = Depends(get_current_user), svc: WorkspaceService = Depends(get_workspace_service)):
    return await svc.rename(id, payload.name, current_user.id)


@router.delete("/{id}", summary="Delete workspace (owner only)")
async def delete(id: int, current_user: User = Depends(get_current_user), svc: WorkspaceService = Depends(get_workspace_service)):
    await svc.delete(id, current_user.id)
    return {"detail": "Workspace deleted."}


@router.post("/{id}/invites", response_model=InviteResponse, status_code=status.HTTP_201_CREATED,
    summary="Invite member to workspace")
async def invite(id: int, payload: InviteCreate, current_user: User = Depends(get_current_user), svc: WorkspaceService = Depends(get_workspace_service)):
    return await svc.invite(id, payload.email, payload.role, current_user.id)


@router.get("/{id}/invites", response_model=List[InviteResponse],
    summary="List workspace invites")
async def list_invites(id: int, current_user: User = Depends(get_current_user), svc: WorkspaceService = Depends(get_workspace_service)):
    return await svc.list_invites(id, current_user.id)


@router.delete("/{id}/invites/{invite_id}",
    summary="Cancel workspace invite")
async def cancel_invite(id: int, invite_id: int, current_user: User = Depends(get_current_user), svc: WorkspaceService = Depends(get_workspace_service)):
    await svc.cancel_invite(id, invite_id, current_user.id)
    return {"detail": "Invite cancelled."}


@router.post("/invites/accept",
    summary="Accept workspace invite")
async def accept_invite(payload: AcceptInviteRequest, current_user: User = Depends(get_current_user), svc: WorkspaceService = Depends(get_workspace_service)):
    return await svc.accept_invite(payload.token, current_user.id)


@router.get("/{id}/members", response_model=List[MemberResponse],
    summary="List workspace members")
async def list_members(id: int, current_user: User = Depends(get_current_user), svc: WorkspaceService = Depends(get_workspace_service)):
    return await svc.list_members(id, current_user.id)


@router.delete("/{id}/members/{member_id}",
    summary="Remove workspace member")
async def remove_member(id: int, member_id: int, current_user: User = Depends(get_current_user), svc: WorkspaceService = Depends(get_workspace_service)):
    await svc.remove_member(id, member_id, current_user.id)
    return {"detail": "Member removed."}


@router.put("/{id}/members/{member_id}/role",
    summary="Update member role")
async def update_member_role(id: int, member_id: int, payload: UpdateMemberRole, current_user: User = Depends(get_current_user), svc: WorkspaceService = Depends(get_workspace_service)):
    return await svc.update_member_role(id, member_id, payload.role, current_user.id)
