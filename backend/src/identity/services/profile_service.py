from src.analytics.services.audit_service import AuditService
from src.identity.models.user import User
from src.identity.repositories.user_repository import UserRepository
from src.identity.services.session_revocation import revoke_refresh_family
from src.shared.core.security import hash_password_async, verify_password_async
from src.shared.errors import EmailAlreadyExists, InvalidCredentials


class _NullAudit:
    async def log(self, **kwargs) -> None:  # noqa: ARG002
        return None


class ProfileService:
    def __init__(self, repo: UserRepository, audit: AuditService | None = None):
        self.repo = repo
        self._audit = audit or _NullAudit()

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not await verify_password_async(current_password, user.password_hash):
            await self._audit.log(
                actor_id=user.id,
                action="password_change_failed",
                resource_type="user",
                resource_id=user.id,
            )
            raise InvalidCredentials()
        await self.repo.update(user.id, password_hash=await hash_password_async(new_password))
        # Sign out everywhere, including this session. A password change is an
        # explicit statement that previous credentials are no longer trusted;
        # leaving refresh tokens alive means a stolen one still works.
        await revoke_refresh_family(user.id)
        await self._audit.log(
            actor_id=user.id,
            action="password_changed",
            resource_type="user",
            resource_id=user.id,
        )

    async def change_email(self, user: User, current_password: str, new_email: str) -> None:
        if not await verify_password_async(current_password, user.password_hash):
            raise InvalidCredentials()
        if await self.repo.email_exists(new_email):
            raise EmailAlreadyExists()
        # Changing the address invalidates every OAuth link: the provider's
        # verified proof was for the *old* address, so keeping github_id/
        # google_id bound would let a stale provider identity re-attach to a
        # re-pointed address. Re-authentication re-establishes it.
        await self.repo.update(
            user.id,
            email=new_email,
            is_verified=False,
            google_id=None,
            github_id=None,
            oauth_provider=None,
        )
        await self._audit.log(
            actor_id=user.id,
            action="email_changed",
            resource_type="user",
            resource_id=user.id,
            before={"email": user.email},
            after={"email": new_email},
        )

    async def upload_avatar(self, user: User, avatar: str) -> None:
        await self.repo.update(user.id, avatar_url=avatar)
