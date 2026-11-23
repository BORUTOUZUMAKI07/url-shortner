import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analytics.services.audit_service import AuditService
from src.identity.models.user import User
from src.identity.repositories.api_key_repository import APIKeyRepository
from src.identity.repositories.user_repository import UserRepository
from src.identity.services.session_revocation import revoke_refresh_family
from src.identity.services.two_factor_service import (
    build_otpauth_uri,
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_recovery_codes,
    generate_totp_secret,
    hash_recovery_codes,
    qr_data_uri,
    verify_recovery_code,
    verify_totp_code,
)
from src.links.models.favorite import Favorite
from src.links.models.url import URL
from src.links.repositories.favorite_repository import FavoriteRepository
from src.links.repositories.url_repository import URLRepository
from src.shared.core.redis import redis_client
from src.shared.core.security import hash_password_async, verify_password_async
from src.shared.errors import EmailAlreadyExists, IncorrectCurrentPassword
from src.workspaces.repositories.workspace_repository import WorkspaceRepository


class _NullAudit:
    async def log(self, **kwargs) -> None:  # noqa: ARG002
        return None


class ProfileService:
    def __init__(
        self,
        repo: UserRepository,
        audit: AuditService | None = None,
        workspace_repo: WorkspaceRepository | None = None,
        url_repo: URLRepository | None = None,
        api_key_repo: APIKeyRepository | None = None,
        favorite_repo: FavoriteRepository | None = None,
        db: AsyncSession | None = None,
    ):
        self.repo = repo
        self._audit = audit or _NullAudit()
        self.workspace_repo = workspace_repo
        self.url_repo = url_repo
        self.api_key_repo = api_key_repo
        self.favorite_repo = favorite_repo
        self.db = db

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not await verify_password_async(current_password, user.password_hash):
            await self._audit.log(
                actor_id=user.id,
                action="password_change_failed",
                resource_type="user",
                resource_id=user.id,
            )
            raise IncorrectCurrentPassword()
        await self.repo.update(user.id, password_hash=await hash_password_async(new_password))
        await revoke_refresh_family(user.id)
        await self._audit.log(
            actor_id=user.id,
            action="password_changed",
            resource_type="user",
            resource_id=user.id,
        )

    async def change_email(self, user: User, current_password: str, new_email: str) -> None:
        if not await verify_password_async(current_password, user.password_hash):
            raise IncorrectCurrentPassword()
        if await self.repo.email_exists(new_email):
            raise EmailAlreadyExists()
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

    # --- 2FA / TOTP ---

    async def two_factor_status(self, user: User) -> dict:
        remaining = 0
        if user.two_factor_recovery_codes:
            try:
                remaining = len(json.loads(user.two_factor_recovery_codes))
            except Exception:
                remaining = 0
        return {
            "enabled": bool(user.two_factor_enabled),
            "confirmed_at": user.two_factor_confirmed_at,
            "recovery_codes_remaining": remaining,
        }

    async def begin_two_factor_setup(self, user: User, current_password: str) -> dict:
        if not await verify_password_async(current_password, user.password_hash):
            raise IncorrectCurrentPassword()
        secret = generate_totp_secret()
        encrypted = encrypt_totp_secret(secret)
        await self.repo.update(user.id, totp_secret_encrypted=encrypted, two_factor_enabled=False, totp_last_counter=None, two_factor_confirmed_at=None)
        uri = build_otpauth_uri(user.email, secret)
        await self._audit.log(actor_id=user.id, action="2fa_setup_started", resource_type="user", resource_id=user.id)
        return {
            "secret": secret,
            "otpauth_uri": uri,
            "qr_code_data_uri": qr_data_uri(uri),
        }

    async def confirm_two_factor_setup(self, user: User, code: str) -> dict:
        fresh = await self.repo.get(user.id)
        if not fresh or not fresh.totp_secret_encrypted:
            from src.shared.errors import BadRequestError

            raise BadRequestError("2FA setup not started")
        secret = decrypt_totp_secret(fresh.totp_secret_encrypted)
        counter = verify_totp_code(secret, code, fresh.totp_last_counter)
        if counter is None:
            from src.shared.errors import UnauthorizedError

            raise UnauthorizedError("Invalid two-factor authentication code")
        recovery_codes = generate_recovery_codes()
        await self.repo.update(
            fresh.id,
            two_factor_enabled=True,
            totp_last_counter=counter,
            two_factor_confirmed_at=datetime.now(timezone.utc),
            two_factor_recovery_codes=hash_recovery_codes(recovery_codes),
        )
        await self._audit.log(actor_id=fresh.id, action="2fa_enabled", resource_type="user", resource_id=fresh.id)
        return {"recovery_codes": recovery_codes}

    async def disable_two_factor(self, user: User, current_password: str, code: str) -> None:
        if not await verify_password_async(current_password, user.password_hash):
            raise IncorrectCurrentPassword()
        fresh = await self.repo.get(user.id)
        if not fresh or not fresh.two_factor_enabled or not fresh.totp_secret_encrypted:
            from src.shared.errors import BadRequestError

            raise BadRequestError("Two-factor authentication is not enabled")
        secret = decrypt_totp_secret(fresh.totp_secret_encrypted)
        counter = verify_totp_code(secret, code, fresh.totp_last_counter)
        ok = counter is not None
        remaining_codes = fresh.two_factor_recovery_codes
        if not ok:
            ok, remaining_codes = verify_recovery_code(fresh.two_factor_recovery_codes, code)
        if not ok:
            from src.shared.errors import UnauthorizedError

            raise UnauthorizedError("Invalid two-factor authentication code")
        await self.repo.update(
            fresh.id,
            two_factor_enabled=False,
            totp_secret_encrypted=None,
            totp_last_counter=None,
            two_factor_recovery_codes=None,
            two_factor_confirmed_at=None,
        )
        await revoke_refresh_family(fresh.id)
        await self._audit.log(actor_id=fresh.id, action="2fa_disabled", resource_type="user", resource_id=fresh.id)

    async def regenerate_recovery_codes(self, user: User, current_password: str, code: str) -> dict:
        if not await verify_password_async(current_password, user.password_hash):
            raise IncorrectCurrentPassword()
        fresh = await self.repo.get(user.id)
        if not fresh or not fresh.two_factor_enabled or not fresh.totp_secret_encrypted:
            from src.shared.errors import BadRequestError

            raise BadRequestError("Two-factor authentication is not enabled")
        secret = decrypt_totp_secret(fresh.totp_secret_encrypted)
        counter = verify_totp_code(secret, code, fresh.totp_last_counter)
        if counter is None:
            from src.shared.errors import UnauthorizedError

            raise UnauthorizedError("Invalid two-factor authentication code")
        recovery_codes = generate_recovery_codes()
        await self.repo.update(fresh.id, two_factor_recovery_codes=hash_recovery_codes(recovery_codes), totp_last_counter=counter)
        await self._audit.log(actor_id=fresh.id, action="2fa_recovery_codes_regenerated", resource_type="user", resource_id=fresh.id)
        return {"recovery_codes": recovery_codes}

    # --- Account export / delete ---

    async def export_account(self, user: User) -> dict:
        if not self.db:
            from src.shared.errors import InternalError

            raise InternalError("Export not available")
        uid = user.id
        profile = {
            "id": user.id,
            "email": user.email,
            "is_verified": user.is_verified,
            "is_active": user.is_active,
            "is_superadmin": user.is_superadmin,
            "avatar_url": user.avatar_url,
            "two_factor_enabled": user.two_factor_enabled,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
        workspaces = []
        if self.workspace_repo:
            owned = await self.workspace_repo.get_many(owner_id=uid, limit=1000)
            for ws in owned:
                workspaces.append({"id": ws.id, "name": ws.name, "role": "owner", "created_at": ws.created_at.isoformat() if ws.created_at else None})
        # Include memberships
        from src.workspaces.models.workspace import Workspace
        from src.workspaces.models.workspace_member import WorkspaceMember

        member_rows = (await self.db.execute(
            select(WorkspaceMember, Workspace)
            .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == uid)
        )).all()
        seen_ws = {w["id"] for w in workspaces}
        for m, ws in member_rows:
            if ws.id in seen_ws:
                continue
            workspaces.append({"id": ws.id, "name": ws.name, "role": m.role.value if hasattr(m.role, "value") else str(m.role), "created_at": ws.created_at.isoformat() if ws.created_at else None})

        links = []
        url_rows = (await self.db.execute(select(URL).where(URL.user_id == uid))).scalars().all()
        for u in url_rows:
            links.append({
                "id": u.id,
                "short_code": u.short_code,
                "original_url": u.original_url,
                "workspace_id": u.workspace_id,
                "status": u.status.value if hasattr(u.status, "value") else str(u.status),
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "expires_at": u.expires_at.isoformat() if u.expires_at else None,
            })

        api_keys = []
        if self.api_key_repo:
            keys = await self.api_key_repo.get_user_keys(uid)
            for k in keys:
                api_keys.append({
                    "id": k.id,
                    "name": k.name,
                    "prefix": k.prefix,
                    "status": k.status.value if hasattr(k.status, "value") else str(k.status),
                    "created_at": k.created_at.isoformat() if k.created_at else None,
                    "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                    "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                })

        favorites = []
        fav_rows = (await self.db.execute(select(Favorite).where(Favorite.user_id == uid))).scalars().all()
        for f in fav_rows:
            favorites.append({"id": f.id, "url_id": f.url_id, "created_at": f.created_at.isoformat() if f.created_at else None})

        export = {
            "exported_at": datetime.now(timezone.utc),
            "profile": profile,
            "workspaces": workspaces,
            "links": links,
            "api_keys": api_keys,
            "favorites": favorites,
            "audit_retention_policy": {
                "audit_logs": "Retained for security and compliance. Actor reference is anonymized when an account is deleted.",
                "analytics": "URL analytics associated with deleted links/workspaces are removed with those resources.",
                "sessions": "Revoked immediately on account deletion.",
            },
        }
        await self._audit.log(actor_id=uid, action="account_exported", resource_type="user", resource_id=uid)
        return export

    async def delete_account(self, user: User, current_password: str, confirmation: str) -> None:
        if confirmation != "DELETE":
            from src.shared.errors import BadRequestError

            raise BadRequestError("Confirmation must be DELETE")
        if not await verify_password_async(current_password, user.password_hash):
            raise IncorrectCurrentPassword()
        uid = user.id

        # Revoke sessions/tokens first.
        await revoke_refresh_family(uid)
        try:
            # remove session index keys
            sids = await redis_client.smembers(f"refresh:user:sessions:{uid}")
            for raw_sid in sids or []:
                sid = raw_sid.decode() if isinstance(raw_sid, (bytes, bytearray)) else str(raw_sid)
                await redis_client.delete(f"refresh:session:{sid}")
            await redis_client.delete(f"refresh:user:sessions:{uid}")
        except Exception:
            pass

        await self._audit.log(actor_id=uid, action="account_delete_requested", resource_type="user", resource_id=uid)

        # Deleting the user row cascades owned workspaces/links/api keys/favorites/memberships
        # per FK constraints; audit_logs.actor_id is SET NULL.
        fresh = await self.repo.get(uid)
        if fresh:
            await self.repo.delete(fresh.id)
        await self._audit.log(actor_id=None, action="account_deleted", resource_type="user", resource_id=uid, before={"user_id": uid})
