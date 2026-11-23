from fastapi import APIRouter, Depends, status

from src.identity.models.user import User
from src.identity.schemas.profile import (
    AccountDeleteRequest,
    AccountExportResponse,
    AvatarUpdateRequest,
    ChangeEmailRequest,
    ChangePasswordRequest,
    RecoveryCodesResponse,
    TwoFactorConfirmRequest,
    TwoFactorDisableRequest,
    TwoFactorSetupRequest,
    TwoFactorSetupResponse,
    TwoFactorStatusResponse,
)
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
    return {"detail": "Email changed successfully."}


@router.post("/avatar", summary="Upload avatar")
async def upload_avatar(
    payload: AvatarUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    await service.upload_avatar(current_user, payload.avatar)
    return {"detail": "Avatar updated successfully.", "avatar_url": payload.avatar}


@router.get("/2fa", response_model=TwoFactorStatusResponse, summary="Get 2FA status")
async def two_factor_status(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    return await service.two_factor_status(current_user)


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse, summary="Begin 2FA setup")
async def two_factor_setup(
    payload: TwoFactorSetupRequest,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    return await service.begin_two_factor_setup(current_user, payload.current_password)


@router.post("/2fa/confirm", response_model=RecoveryCodesResponse, summary="Confirm 2FA setup")
async def two_factor_confirm(
    payload: TwoFactorConfirmRequest,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    return await service.confirm_two_factor_setup(current_user, payload.code)


@router.post("/2fa/disable", summary="Disable 2FA")
async def two_factor_disable(
    payload: TwoFactorDisableRequest,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    await service.disable_two_factor(current_user, payload.current_password, payload.code)
    return {"detail": "Two-factor authentication disabled."}


@router.post("/2fa/recovery-codes", response_model=RecoveryCodesResponse, summary="Regenerate 2FA recovery codes")
async def two_factor_regenerate_recovery_codes(
    payload: TwoFactorDisableRequest,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    return await service.regenerate_recovery_codes(current_user, payload.current_password, payload.code)


@router.get("/export", response_model=AccountExportResponse, summary="Export account data")
async def export_account(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    return await service.export_account(current_user)


@router.delete("/account", status_code=status.HTTP_200_OK, summary="Delete account")
async def delete_account(
    payload: AccountDeleteRequest,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    await service.delete_account(current_user, payload.current_password, payload.confirmation)
    return {"detail": "Account deleted."}
