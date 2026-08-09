from fastapi import APIRouter, Depends, status

from src.identity.models.user import User
from src.identity.schemas.profile import AvatarUpdateRequest, ChangeEmailRequest, ChangePasswordRequest
from src.identity.services.profile_service import ProfileService
from src.shared.core.deps import get_current_user, get_profile_service

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.put("/password", summary="Change password")
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    await service.change_password(current_user, payload.current_password, payload.new_password)
    return {"detail": "Password changed successfully."}


@router.put("/email", summary="Change email")
async def change_email(
    payload: ChangeEmailRequest,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    await service.change_email(current_user, payload.current_password, payload.new_email)
    return {"detail": "Email changed. Please verify your new email address."}


@router.post("/avatar", summary="Upload avatar", status_code=status.HTTP_200_OK)
async def upload_avatar(
    payload: AvatarUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    await service.upload_avatar(current_user, payload.avatar)
    return {"detail": "Avatar updated.", "avatar_url": payload.avatar}
