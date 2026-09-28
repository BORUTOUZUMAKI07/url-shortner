import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from collections.abc import Callable
from typing import Any

from jose import JWTError

from src.identity.models.user import User
from src.identity.repositories.user_repository import UserRepository
from src.identity.schemas.user import Token
from src.identity.services.email_service import EmailService
from src.identity.services.session_revocation import (
    is_family_revoked,
    revoke_refresh_family,
)
from src.shared.core.config import settings
from src.shared.core.redis import redis_client
from src.shared.core.security import (
    create_access_token,
    create_email_verification_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password_async,
    reset_fingerprint,
    verify_password_async,
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
    UnauthorizedError,
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
_REUSE_GRACE_SECONDS = 30  # tolerate legit duplicate refreshes (network retries/concurrent 401s)

_ROTATE_REFRESH_LUA = """
local rec = redis.call('GET', KEYS[1])
if not rec then
    return -1
end
-- Redis Lua exposes no os.time(); TIME is the sandbox-safe clock.
local now = tonumber(redis.call('TIME')[1])
local presented = ARGV[1]
local new_jti = ARGV[2]
local grace = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])
local obj = cjson.decode(rec)
if obj.jti == presented then
    obj.prev_jti = obj.jti
    obj.prev_at = now
    obj.jti = new_jti
    redis.call('SET', KEYS[1], cjson.encode(obj), 'EX', ttl)
    return 1
end
if obj.prev_jti == presented and (now - (obj.prev_at or 0)) <= grace then
    obj.prev_jti = obj.jti
    obj.prev_at = now
    obj.jti = new_jti
    redis.call('SET', KEYS[1], cjson.encode(obj), 'EX', ttl)
    return 1
end
return 0
"""


# Read AND delete both single-use OAuth callback keys in one atomic round trip.
#
# These used to be mget() then delete_many() — two serial Upstash REST calls, with
# a window between them in which a crash left the state replayable. Lua runs the
# read and the delete as a single indivisible step, so the value can never be
# observed by a second caller, and a crash cannot leave a live state behind.
#
# Both keys are consumed unconditionally, even when the caller goes on to reject
# the callback: a state that fails CSRF must not stay valid for a retry. That
# matches the previous behaviour deliberately.
#
# Lua cannot put nil in a table, so a missing key is reported as false.
_CONSUME_OAUTH_STATE_LUA = """
local state = redis.call('GET', KEYS[1])
local pkce = redis.call('GET', KEYS[2])
if state or pkce then
    redis.call('DEL', KEYS[1], KEYS[2])
end
return {state or false, pkce or false}
"""

# Writes the state and the PKCE verifier together, so they are either both
# present or both absent.
#
# This is the same reasoning as _CONSUME_OAUTH_STATE_LUA applied at creation
# time, and the failure it closes is a real one: two separate SETEX calls meant
# a transient Upstash error between them left a state with no verifier. The
# callback then resolved `code_verifier = None` and called
# `authenticate(code, code_verifier=None)` — a token exchange with **no PKCE
# at all**, silently, after having advertised a code_challenge to the provider.
# The code is single-use and short-lived, so nothing looks wrong; PKCE simply
# stops existing for that one sign-in.
#
# One script is also one REST round trip instead of two. On Upstash each command
# is a separate HTTPS request (~100-200ms from Render), and this pair was
# serial, so it sat directly in front of the redirect to the provider.
_INIT_OAUTH_STATE_LUA = """
redis.call('SETEX', KEYS[1], ARGV[1], ARGV[2])
redis.call('SETEX', KEYS[2], ARGV[1], ARGV[3])
return 1
"""


def _refresh_session_ttl() -> int:
    """Redis TTL for a session record. Must not outlive the refresh token it
    tracks, or a record would outlive every token that could ever be checked
    against it."""
    return settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600


class _NullAudit:
    """Stand-in used when no AuditService is wired (unit tests, scripts)."""

    async def log(self, **kwargs) -> None:  # noqa: ARG002
        return None


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        workspace_repo: WorkspaceRepository,
        audit=None,
    ):
        self.user_repo = user_repo
        self.workspace_repo = workspace_repo
        self._audit = audit or _NullAudit()

    async def register(self, email: str, password: str):
        if await self.user_repo.email_exists(email):
            raise EmailAlreadyExists()

        user = await self.user_repo.create(
            email=email,
            password_hash=await hash_password_async(password),
        )
        await self.workspace_repo.create_default(user.id)

        verification_token = create_email_verification_token(user.email)
        await EmailService.send_verification_email(email, verification_token)
        await self._audit.log(
            actor_id=user.id,
            action="register",
            resource_type="user",
            resource_id=user.id,
        )
        return user

    async def login(self, email: str, password: str) -> Token:
        user = await self.user_repo.get_by_email(email)
        if not user or not await verify_password_async(password, user.password_hash):
            # Audit the failure too: credential stuffing against a known
            # address is otherwise invisible.
            await self._audit.log(
                actor_id=user.id if user else None,
                action="login_failed",
                resource_type="user",
                resource_id=user.id if user else None,
                after={"email": email},
            )
            raise InvalidCredentials()
        if not user.is_active:
            await self._audit.log(
                actor_id=user.id,
                action="login_blocked_inactive",
                resource_type="user",
                resource_id=user.id,
            )
            raise UnauthorizedError("Account is deactivated")
        if settings.REQUIRE_EMAIL_VERIFICATION and not user.is_verified:
            raise UnauthorizedError("Email address is not verified")
        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})
        await self._store_refresh_session(refresh_token, user.id)
        await self._audit.log(
            actor_id=user.id,
            action="login",
            resource_type="user",
            resource_id=user.id,
        )
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
        if not user.is_active:
            raise UnauthorizedError("Account is deactivated")

        new_access = create_access_token(data={"sub": str(user.id)})

        if sid and jti:
            # Tokens minted with session metadata get reuse detection: if the
            # presented token's jti no longer matches the session record, it was
            # already rotated out — someone is replaying it.
            if await is_family_revoked(user.id):
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
                str(_refresh_session_ttl()),
            )
            result = int(result)
            if result == 0:
                # Reuse detected — the presented token was already rotated out.
                # Revoke the whole refresh-token family for this user.
                await revoke_refresh_family(user.id)
                await self._audit.log(
                    actor_id=user.id,
                    action="refresh_token_reuse_detected",
                    resource_type="user",
                    resource_id=user.id,
                    after={"sid": sid},
                )
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
            await redis_client.setex(
                f"{_REFRESH_SESSION_PREFIX}{sid}", _refresh_session_ttl(), record
            )
        except Exception as e:
            logger.warning("Failed to store refresh session: %s", e)

    async def create_oauth_handoff(self, refresh_token: str) -> str:
        """Issue a short-lived one-time code exchangeable for the refresh token.

        The refresh token itself is never placed in the OAuth callback redirect
        URL (URLs leak via access logs / Referer headers).
        """
        code = secrets.token_urlsafe(32)
        await redis_client.setex(f"oauth:handoff:{code}", 120, refresh_token)
        return code

    async def exchange_oauth_handoff(self, code: str) -> str:
        """One-time exchange of an OAuth handoff code for the refresh token.

        GETDEL, not get()+delete(): the await between those two calls let two
        concurrent requests both read the token before either deleted it, so a
        code documented as single-use was redeemable twice. getdel is atomic, so
        exactly one caller can win — and it is one Upstash REST round trip
        instead of two.
        """
        if not code:
            raise InvalidToken()
        token = await redis_client.getdel(f"oauth:handoff:{code}")
        if not token:
            raise InvalidToken()
        return token  # type: ignore[no-any-return]

    async def logout(self, token: str) -> None:
        actor_id: int | None = None
        try:
            payload = decode_token(token)
            sub = payload.get("sub")
            if sub and str(sub).isdigit():
                actor_id = int(sub)
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
        if actor_id is not None:
            await self._audit.log(
                actor_id=actor_id,
                action="logout",
                resource_type="user",
                resource_id=actor_id,
            )

    async def forgot_password(self, email: str) -> None:
        user = await self.user_repo.get_by_email(email)
        if not user:
            # Do not disclose whether the address exists, but the attempt is
            # still worth an audit row.
            await self._audit.log(
                action="password_reset_requested_unknown_email",
                resource_type="user",
                after={"email": email},
            )
            return
        reset_token = create_password_reset_token(user.email, user.password_hash)
        await EmailService.send_password_reset(email, reset_token)
        await self._audit.log(
            actor_id=user.id,
            action="password_reset_requested",
            resource_type="user",
            resource_id=user.id,
        )

    async def reset_password(self, token: str, new_password: str) -> None:
        token_payload = decode_token(token)
        email = token_payload.get("sub")
        token_type = token_payload.get("type")
        if not email or token_type != "reset":
            raise InvalidResetToken()
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise UserNotFound()
        # The token is bound to the password it was issued against. Once that
        # password has been changed the binding no longer matches, so a reset
        # link that leaked cannot be replayed after the owner already used it -
        # which would otherwise be account takeover, not a nuisance.
        if not hmac.compare_digest(
            str(token_payload.get("pfp", "")), reset_fingerprint(user.password_hash)
        ):
            raise InvalidResetToken()
        await self.user_repo.update(user.id, password_hash=await hash_password_async(new_password))
        # Changing the password must invalidate every existing session. Without
        # this, a stolen refresh token keeps working after the owner has
        # explicitly reset their credentials, which defeats the reset entirely.
        await revoke_refresh_family(user.id)
        await self._audit.log(
            actor_id=user.id,
            action="password_reset",
            resource_type="user",
            resource_id=user.id,
        )

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
        await self._audit.log(
            actor_id=user.id,
            action="email_verified",
            resource_type="user",
            resource_id=user.id,
        )

    async def resend_verification(self, user: User) -> bool:
        """Re-issue the verification link for an authenticated, unverified user.

        Without this the only way to ever become verified is the single mail
        sent at signup: lose it, or let the 24h token lapse, and the profile page
        shows "Email not verified" permanently with no way out.

        Returns False when the server has no SMTP configured, so the caller can
        say so instead of pretending a mail is on its way. `EmailService._send`
        swallows a missing configuration (it just logs "Would send email to...")
        *and* every send failure, so without this signal the user is told to
        "check your inbox" for a message that will never arrive anywhere.
        """
        if user.is_verified:
            return True  # nothing left to confirm; stay quiet, not an error
        if not EmailService.is_configured():
            await self._audit.log(
                actor_id=user.id,
                action="verification_resend_unavailable",
                resource_type="user",
                resource_id=user.id,
                after={"reason": "smtp_not_configured"},
            )
            return False
        token = create_email_verification_token(user.email)
        await EmailService.send_verification_email(user.email, token)
        await self._audit.log(
            actor_id=user.id,
            action="verification_email_resent",
            resource_type="user",
            resource_id=user.id,
        )
        return True

    async def oauth_init(self, provider: str) -> tuple[str, str]:
        from src.identity.services.sso import SSOProviderRegistry
        oauth = SSOProviderRegistry.get(provider)
        if not oauth or not oauth.is_configured():
            raise OAuthNotConfigured(provider)
        state = secrets.token_urlsafe(32)
        # PKCE (RFC 7636): a per-request code verifier is stored server-side;
        # its S256 challenge rides the authorize URL and the verifier is posted
        # with the token exchange. A stolen authorization code can't be traded
        # for tokens without the verifier.
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        # Written together, in one round trip. See _INIT_OAUTH_STATE_LUA: two
        # separate SETEX calls could leave the state without its verifier, and
        # the callback degrades a missing verifier to `None` — which means no
        # PKCE, silently.
        await redis_client.eval(
            _INIT_OAUTH_STATE_LUA,
            2,
            f"oauth:state:{state}",
            f"oauth:pkce:{state}",
            "600",
            "1",
            code_verifier,
        )
        auth_url = oauth.get_authorization_url(state, code_challenge=code_challenge)
        return auth_url, state

    async def oauth_callback(self, provider: str, code: str, state: str) -> Token:
        from src.identity.services.sso import SSOProviderRegistry
        oauth = SSOProviderRegistry.get(provider)
        if not oauth or not oauth.is_configured():
            raise OAuthNotConfigured(provider)

        # Per-phase timings. This handler was reported as taking ~2s and the
        # cause was genuinely unknown — four candidate explanations (a provider
        # round trip, a cold Neon connection, a Render cold start, or Upstash)
        # all fit the symptom, and nothing in the logs distinguished them. The
        # breakdown is logged unconditionally, on success and on failure, so the
        # next occurrence identifies itself. Without a number the only honest
        # answer is "unknown", and a guess would be worse than no answer.
        #
        # The phases are NOT independent costs. `provider_exchange` blocks on two
        # HTTPS calls to the provider, and every database phase below can absorb
        # a cold-start wake — Neon's free tier suspends the compute after ~5 min
        # idle, so the first query of a quiet period pays for it. The split
        # exists to tell those apart, and a single `db_*` phase being large
        # while the others are small is the signature of a cold connection.
        _phases: dict[str, float] = {}
        _last = time.perf_counter()

        def _lap(name: str) -> None:
            nonlocal _last
            now = time.perf_counter()
            _phases[name] = (now - _last) * 1000
            _last = now

        try:
            return await self._run_oauth_callback(provider, oauth, code, state, _lap)
        finally:
            logger.info(
                "oauth_callback timings provider=%s total=%.0fms %s",
                provider,
                sum(_phases.values()),
                " ".join(f"{k}={v:.0f}ms" for k, v in _phases.items()),
            )

    async def _run_oauth_callback(
        self,
        provider: str,
        oauth: Any,
        code: str,
        state: str,
        _lap: Callable[[str], None],
    ) -> Token:
        # One atomic round trip: read both single-use keys and delete them. The
        # state and the PKCE verifier are consumed together, so a failure below
        # cannot leave a replayable state behind.
        state_value, code_verifier = await redis_client.eval(
            _CONSUME_OAUTH_STATE_LUA,
            2,
            f"oauth:state:{state}",
            f"oauth:pkce:{state}",
        )
        _lap("redis_state_pkce")
        if not state_value:
            raise CSRFValidationFailed()
        # Lua reports a missing key as false; normalise to None so the provider
        # sees "no verifier" rather than a boolean.
        if not code_verifier:
            code_verifier = None

        user_info = await oauth.authenticate(code, code_verifier=code_verifier)
        _lap("provider_exchange")
        if not user_info:
            raise OAuthFailed(provider)

        # An OAuth identity is only as trustworthy as the provider's proof that
        # the account controls the email. Google and GitHub both return that
        # proof; a provider (or a future integration) that omits it must not be
        # able to mint a login, so `is not True` rather than `is False` -
        # a missing claim is a missing claim.
        if user_info.get("verified_email") is not True:
            raise OAuthFailed(provider)

        subject = str(user_info.get("id") or "").strip()
        email = user_info.get("email")
        if not subject or not email:
            raise OAuthFailed(provider)

        try:
            # Identity is established by the provider subject, never by email.
            # Email is only consulted to *find a pre-existing account to link*,
            # and only once the address is known-verified.
            user = await self.user_repo.get_by_oauth_sub(provider, subject)
            _lap("db_lookup_by_sub")
            if user is None and await self.user_repo.email_exists(email):
                candidate = await self.user_repo.get_by_email(email)
                _lap("db_lookup_by_email")
                # Refuse to merge into an account already bound to a different
                # provider subject: that is either a provider account-takeover
                # or a genuine user confusion, and silently re-binding would
                # hand the account to whoever holds the second identity.
                if candidate and candidate.oauth_provider and candidate.oauth_provider != provider:
                    raise OAuthFailed(provider)
                user = candidate

            if not user:
                # Argon2 is deliberately CPU-bound (~100-300ms). It runs in a
                # thread via `hash_password_async` so it cannot block the loop,
                # but it is still real wall-clock on the request — and it only
                # happens on a user's *first* OAuth sign-in, which is exactly
                # when someone is timing how fast sign-in feels. Timed
                # separately from the INSERT so a slow first login does not get
                # misread as a slow database.
                user = await self.user_repo.create(
                    email=email,
                    password_hash=await hash_password_async(secrets.token_urlsafe(32)),
                    **{self._sub_column(provider): subject},
                    oauth_provider=provider,
                    oauth_avatar_url=user_info.get("picture"),
                    is_verified=True,
                )
                _lap("argon2_hash_new_user")
                await self.workspace_repo.create_default(user.id)
                _lap("db_create_default_workspace")
            else:
                if not user.is_active:
                    raise UnauthorizedError("Account is deactivated")
                update_fields: dict[str, object] = {}
                if not getattr(user, self._sub_column(provider)):
                    update_fields[self._sub_column(provider)] = subject
                if not user.oauth_provider:
                    update_fields["oauth_provider"] = provider
                if not user.oauth_avatar_url and user_info.get("picture"):
                    update_fields["oauth_avatar_url"] = user_info.get("picture")
                # The provider has verified the address it handed us, and it
                # matches the address on the account, so verification is earned.
                if not user.is_verified:
                    update_fields["is_verified"] = True
                if update_fields:
                    await self.user_repo.update(user.id, **update_fields)
                    _lap("db_update_user")

            await self._audit.log(
                actor_id=user.id,
                action=f"oauth_login.{provider}",
                resource_type="user",
                resource_id=user.id,
            )
            _lap("db_audit_log")
            access_token = create_access_token(data={"sub": str(user.id)})
            refresh_token = create_refresh_token(data={"sub": str(user.id)})
            _lap("mint_tokens")
            await self._store_refresh_session(refresh_token, user.id)
            _lap("redis_store_session")
            return Token(access_token=access_token, token_type="bearer", refresh_token=refresh_token)
        except OAuthFailed:
            raise
        except Exception as e:
            logger.error(f"OAuth callback error for {provider}: {e}", exc_info=True)
            raise

    @staticmethod
    def _sub_column(provider: str) -> str:
        return {"google": "google_id", "github": "github_id"}.get(provider, "google_id")
