from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.identity.models.user import User
from src.identity.repositories.user_repository import UserRepository
from src.identity.schemas.profile import AvatarUpdateRequest, ChangeEmailRequest, ChangePasswordRequest
from src.shared.core.deps import get_current_user, get_db
from src.shared.core.security import hash_password, verify_password
from src.shared.errors import EmailAlreadyExists, InvalidCredentials

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.put("/password", summary="Change password")
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise InvalidCredentials()
    repo = UserRepository(db)
    await repo.update(current_user.id, password_hash=hash_password(payload.new_password))
    return {"detail": "Password changed successfully."}


@router.put("/email", summary="Change email")
async def change_email(
    payload: ChangeEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise InvalidCredentials()
    repo = UserRepository(db)
    if await repo.email_exists(payload.new_email):
        raise EmailAlreadyExists()
    await repo.update(current_user.id, email=payload.new_email, is_verified=False)
    return {"detail": "Email changed. Please verify your new email address."}


@router.post("/avatar", summary="Upload avatar", status_code=status.HTTP_200_OK)
async def upload_avatar(
    payload: AvatarUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)
    await repo.update(current_user.id, avatar_url=payload.avatar)
    return {"detail": "Avatar updated.", "avatar_url": payload.avatar}
