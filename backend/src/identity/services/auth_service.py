import logging
import secrets
import time

from jose import JWTError

from src.identity.repositories.user_repository import UserRepository
from src.identity.schemas.user import Token
from src.identity.services.email_service import EmailService
from src.shared.core.redis import redis_client
from src.shared.core.security import (
    create_access_token,
    create_email_verification_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from src.shared.errors import (
    CSRFValidationFailed,
    EmailAlreadyExists,
    InvalidCredentials,
    InvalidResetToken,
    InvalidToken,
    InvalidVerifyToken,
    OAuthFailed,
    OAuthNotConfigured,
    TokenRevoked,
    UserNotFound,
)
from src.workspaces.repositories.workspace_repository import WorkspaceRepository

logger = logging.getLogger("url-shortener")


class AuthService:
    def __init__(self, user_repo: UserRepository, workspace_repo: WorkspaceRepository):
        self.user_repo = user_repo
        self.workspace_repo = workspace_repo

    async def register(self, email: str, password: str):
        if await self.user_repo.email_exists(email):
            raise EmailAlreadyExists()

        user = await self.user_repo.create(
            email=email,
            password_hash=hash_password(password),
        )
        await self.workspace_repo.create_default(user.id)

        verification_token = create_email_verification_token(user.email)
        await EmailService.send_verification_email(email, verification_token)
        return user

    async def login(self, email: str, password: str) -> Token:
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise InvalidCredentials()
        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})
        return Token(access_token=access_token, token_type="bearer", refresh_token=refresh_token)

    async def refresh(self, refresh_token: str) -> Token:
        token_payload = decode_token(refresh_token)
        user_id = token_payload.get("sub")
        token_type = token_payload.get("type")

        if not user_id or token_type != "refresh":
            raise InvalidToken()

        is_blacklisted = await redis_client.get(f"jwt:blacklist:{refresh_token}")
        if is_blacklisted:
            raise TokenRevoked()

        user = await self.user_repo.get(int(user_id))
        if not user:
            raise UserNotFound()

        new_access = create_access_token(data={"sub": str(user.id)})
        new_refresh = create_refresh_token(data={"sub": str(user.id)})

        exp = token_payload.get("exp")
        if exp:
            ttl = exp - int(time.time())
            if ttl > 0:
                await redis_client.setex(f"jwt:blacklist:{refresh_token}", ttl, "1")

        return Token(access_token=new_access, token_type="bearer", refresh_token=new_refresh)

    async def create_oauth_handoff(self, refresh_token: str) -> str:
        """Issue a short-lived one-time code exchangeable for the refresh token.

        The refresh token itself is never placed in the OAuth callback redirect
        URL (URLs leak via access logs / Referer headers).
        """
        code = secrets.token_urlsafe(32)
        await redis_client.setex(f"oauth:handoff:{code}", 120, refresh_token)
        return code

    async def exchange_oauth_handoff(self, code: str) -> str:
        """One-time exchange of an OAuth handoff code for the refresh token."""
        if not code:
            raise InvalidToken()
        key = f"oauth:handoff:{code}"
        token = await redis_client.get(key)
        await redis_client.delete(key)
        if not token:
            raise InvalidToken()
        return token  # type: ignore[no-any-return]

    async def logout(self, token: str) -> None:
        try:
            payload = decode_token(token)
            exp = payload.get("exp")
            if exp:
                ttl = exp - int(time.time())
                if ttl > 0:
                    await redis_client.setex(f"jwt:blacklist:{token}", ttl, "1")
        except JWTError:
            pass

    async def forgot_password(self, email: str) -> None:
        user = await self.user_repo.get_by_email(email)
        if not user:
            return
        reset_token = create_password_reset_token(user.email)
        await EmailService.send_password_reset(email, reset_token)

    async def reset_password(self, token: str, new_password: str) -> None:
        token_payload = decode_token(token)
        email = token_payload.get("sub")
        token_type = token_payload.get("type")
        if not email or token_type != "reset":
            raise InvalidResetToken()
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise UserNotFound()
        await self.user_repo.update(user.id, password_hash=hash_password(new_password))

    async def verify_email(self, token: str) -> None:
        token_payload = decode_token(token)
        email = token_payload.get("sub")
        token_type = token_payload.get("type")
        if not email or token_type != "verify":
            raise InvalidVerifyToken()
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise UserNotFound()
        await self.user_repo.update(user.id, is_verified=True)

    async def oauth_init(self, provider: str) -> tuple[str, str]:
        from src.identity.services.sso import SSOProviderRegistry
        oauth = SSOProviderRegistry.get(provider)
        if not oauth or not oauth.is_configured():
            raise OAuthNotConfigured(provider)
        state = secrets.token_urlsafe(32)
        await redis_client.setex(f"oauth:state:{state}", 600, "1")
        auth_url = oauth.get_authorization_url(state)
        return auth_url, state

    async def oauth_callback(self, provider: str, code: str, state: str) -> Token:
        from src.identity.services.sso import SSOProviderRegistry
        oauth = SSOProviderRegistry.get(provider)
        if not oauth or not oauth.is_configured():
            raise OAuthNotConfigured(provider)

        state_exists = await redis_client.get(f"oauth:state:{state}")
        if not state_exists:
            raise CSRFValidationFailed()
        await redis_client.delete(f"oauth:state:{state}")

        user_info = await oauth.authenticate(code)
        if not user_info:
            raise OAuthFailed(provider)

        try:
            user = await self.user_repo.get_by_email(user_info["email"])
            if not user:
                user = await self.user_repo.create(
                    email=user_info["email"],
                    password_hash=hash_password(secrets.token_urlsafe(32)),
                    google_id=user_info["id"] if provider == "google" else None,
                    oauth_provider=provider,
                    oauth_avatar_url=user_info.get("picture"),
                    is_verified=user_info.get("verified_email", False),
                )
                await self.workspace_repo.create_default(user.id)
            else:
                update_fields = {}
                if provider == "google" and not user.google_id:
                    update_fields["google_id"] = user_info["id"]
                if not user.oauth_provider:
                    update_fields["oauth_provider"] = provider
                    update_fields["oauth_avatar_url"] = user_info.get("picture")
                    if user_info.get("verified_email"):
                        update_fields["is_verified"] = True
                if update_fields:
                    await self.user_repo.update(user.id, **update_fields)

            access_token = create_access_token(data={"sub": str(user.id)})
            refresh_token = create_refresh_token(data={"sub": str(user.id)})
            return Token(access_token=access_token, token_type="bearer", refresh_token=refresh_token)
        except Exception as e:
            logger.error(f"OAuth callback error for {provider}: {e}", exc_info=True)
            raise
