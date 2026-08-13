import base64
import hashlib
import json
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

# Refresh-token reuse detection (OAuth 2.0 BCP / RFC 9700). Each refresh token
# carries a stable sid (session id) and a unique jti. Redis keeps one record per
# session holding the CURRENT jti plus the immediately-previous one (for a short
# grace window). If a presented jti matches neither, the token was rotated out
# already — a replay — so the whole refresh family for the user is revoked.
_REFRESH_SESSION_PREFIX = "refresh:session:"
_REFRESH_REVOKED_PREFIX = "refresh:revoked:"
_REFRESH_TTL = 7 * 24 * 3600  # must stay in sync with create_refresh_token's 7-day exp
_REUSE_GRACE_SECONDS = 30  # tolerate legit duplicate refreshes (network retries/concurrent 401s)

_ROTATE_REFRESH_LUA = """
local rec = redis.call('GET', KEYS[1])
if not rec then
    return -1
end
local presented = ARGV[1]
local new_jti = ARGV[2]
local grace = tonumber(ARGV[3])
local obj = cjson.decode(rec)
if obj.jti == presented then
    obj.prev_jti = obj.jti
    obj.prev_at = os.time()
    obj.jti = new_jti
    redis.call('SET', KEYS[1], cjson.encode(obj), 'EX', 604800)
    return 1
end
if obj.prev_jti == presented and (os.time() - (obj.prev_at or 0)) <= grace then
    obj.prev_jti = obj.jti
    obj.prev_at = os.time()
    obj.jti = new_jti
    redis.call('SET', KEYS[1], cjson.encode(obj), 'EX', 604800)
    return 1
end
return 0
"""


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
        await self._store_refresh_session(refresh_token, user.id)
        return Token(access_token=access_token, token_type="bearer", refresh_token=refresh_token)

    async def refresh(self, refresh_token: str) -> Token:
        payload = decode_token(refresh_token)
        user_id = payload.get("sub")
        token_type = payload.get("type")
        sid = payload.get("sid")
        jti = payload.get("jti")

        if not user_id or token_type != "refresh":
            raise InvalidToken()

        is_blacklisted = await redis_client.get(f"jwt:blacklist:{refresh_token}")
        if is_blacklisted:
            raise TokenRevoked()

        user = await self.user_repo.get(int(user_id))
        if not user:
            raise UserNotFound()

        new_access = create_access_token(data={"sub": str(user.id)})

        if sid and jti:
            # Tokens minted with session metadata get reuse detection: if the
            # presented token's jti no longer matches the session record, it was
            # already rotated out — someone is replaying it.
            revoked = await redis_client.get(f"{_REFRESH_REVOKED_PREFIX}{user.id}")
            if revoked:
                raise TokenRevoked()
            new_refresh = create_refresh_token(data={"sub": str(user.id)}, sid=sid)
            new_payload = decode_token(new_refresh)
            result = await redis_client.eval(
                _ROTATE_REFRESH_LUA,
                1,
                f"{_REFRESH_SESSION_PREFIX}{sid}",
                jti,
                new_payload.get("jti", ""),
                str(_REUSE_GRACE_SECONDS),
            )
            result = int(result)
            if result == 0:
                # Reuse detected — the presented token was already rotated out.
                # Revoke the whole refresh-token family for this user.
                await self._revoke_refresh_family(user.id)
                raise TokenRevoked()
            if result == -1:
                # No session record for this sid (Redis lost it or it never
                # existed). Reject rather than rotate — a missing record isn't
                # proof of replay, so no family revocation.
                raise TokenRevoked()
        else:
            # Legacy token (pre-session-metadata): rotate as before, but mint
            # the replacement WITH session metadata so detection applies next time.
            new_refresh = create_refresh_token(data={"sub": str(user.id)})
            await self._store_refresh_session(new_refresh, user.id)

        exp = payload.get("exp")
        if exp:
            ttl = exp - int(time.time())
            if ttl > 0:
                await redis_client.setex(f"jwt:blacklist:{refresh_token}", ttl, "1")

        return Token(access_token=new_access, token_type="bearer", refresh_token=new_refresh)

    async def _store_refresh_session(self, refresh_token: str, user_id: int) -> None:
        """Record a freshly-issued refresh token's sid/jti so rotation and
        reuse detection have a session anchor. Best-effort: if Redis is down we
        can't detect reuse, but the token itself is still valid."""
        try:
            payload = decode_token(refresh_token)
            sid = payload.get("sid")
            jti = payload.get("jti")
            if not sid or not jti:
                return
            record = json.dumps({
                "jti": jti,
                "prev_jti": None,
                "prev_at": 0,
                "created": int(time.time()),
            })
            await redis_client.setex(f"{_REFRESH_SESSION_PREFIX}{sid}", _REFRESH_TTL, record)
        except Exception as e:
            logger.warning("Failed to store refresh session: %s", e)

    async def _revoke_refresh_family(self, user_id: int) -> None:
        """Kill every refresh token for a user (e.g. after a replay is detected
        or a password change). Existing access tokens still live out their short
        expiry; all future refreshes for this user are rejected."""
        try:
            await redis_client.setex(f"{_REFRESH_REVOKED_PREFIX}{user_id}", _REFRESH_TTL, "1")
        except Exception as e:
            logger.warning("Failed to revoke refresh family for user %s: %s", user_id, e)

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
            sid = payload.get("sid")
            if sid:
                await redis_client.delete(f"{_REFRESH_SESSION_PREFIX}{sid}")
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
        # PKCE (RFC 7636): a per-request code verifier is stored server-side;
        # its S256 challenge rides the authorize URL and the verifier is posted
        # with the token exchange. A stolen authorization code can't be traded
        # for tokens without the verifier.
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        await redis_client.setex(f"oauth:pkce:{state}", 600, code_verifier)
        auth_url = oauth.get_authorization_url(state, code_challenge=code_challenge)
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

        code_verifier = await redis_client.get(f"oauth:pkce:{state}")
        await redis_client.delete(f"oauth:pkce:{state}")

        user_info = await oauth.authenticate(code, code_verifier=code_verifier)
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
            await self._store_refresh_session(refresh_token, user.id)
            return Token(access_token=access_token, token_type="bearer", refresh_token=refresh_token)
        except Exception as e:
            logger.error(f"OAuth callback error for {provider}: {e}", exc_info=True)
            raise
