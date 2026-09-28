from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials

from src.identity.models.user import User
from src.identity.schemas.user import (
    ForgotPasswordRequest,
    OAuthExchangeRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    Token,
    TokenWithUser,
    UserCreate,
    UserLogin,
    UserResponse,
    VerifyEmailRequest,
)
from src.identity.services.auth_service import AuthService
from src.identity.services.sso import SSOProviderRegistry
from src.shared.core.client_ip import get_client_ip
from src.shared.core.config import settings
from src.shared.core.deps import (
    bearer_scheme_optional,
    get_auth_service,
    get_current_user,
)
from src.shared.core.redis import check_rate_limit
from src.shared.core.security import create_access_token, decode_token

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    response_description="The newly created user (password excluded)")
async def register(payload: UserCreate, svc: AuthService = Depends(get_auth_service)):
    return await svc.register(payload.email, payload.password)


@router.post("/login", response_model=Token,
    summary="Login",
    description="Authenticate with email and password to receive access and refresh tokens.")
async def login(
    request: Request,
    response: Response,
    payload: UserLogin,
    svc: AuthService = Depends(get_auth_service),
):
    await _enforce_auth_rate_limit(request, "login")
    token = await svc.login(payload.email, payload.password)
    _set_auth_cookies(response, token.access_token, token.refresh_token)
    return token


@router.post("/refresh", response_model=Token,
    summary="Refresh access token")
async def refresh(
    request: Request,
    response: Response,
    payload: Optional[RefreshTokenRequest] = None,
    svc: AuthService = Depends(get_auth_service),
):
    await _enforce_auth_rate_limit(request, "refresh")
    refresh_token = payload.refresh_token if payload and payload.refresh_token else request.cookies.get("refresh_token")
    try:
        if not refresh_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")
        token = await svc.refresh(refresh_token)
    except Exception:
        # A refresh that fails means the refresh cookie is dead: expired,
        # revoked, replayed, or the user's account deactivated. The cookie was
        # httpOnly, so nothing client-side can remove it, and JS cannot even see
        # it. Left in place it is replayed on every subsequent request for the
        # rest of its max_age (7 days by default) — each replay a wasted round
        # trip that also consumes the per-IP `refresh` rate-limit budget, so a
        # stuck client can throttle the user's own next login.
        #
        # Raising here would discard the `response` object and its headers, so
        # the delete has to be sent as the response itself.
        return _refresh_rejected_response()
    _set_auth_cookies(response, token.access_token, token.refresh_token)
    return token


@router.post("/logout",
    summary="Logout",
    description="Blacklists the current access/refresh tokens and clears auth cookies. Does not require a "
                "valid Authorization header so the client can always clear its cookies.")
async def logout(
    request: Request,
    response: Response,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme_optional),
    svc: AuthService = Depends(get_auth_service),
):
    # Best-effort blacklist — an expired/absent token must not block cookie clearing.
    if credentials:
        try:
            await svc.logout(credentials.credentials)
        except Exception:
            pass
    refresh_cookie = request.cookies.get("refresh_token")
    if refresh_cookie:
        try:
            await svc.logout(refresh_cookie)
        except Exception:
            pass
    _clear_auth_cookies(response)
    return {"detail": "Successfully logged out"}


@router.post("/forgot-password",
    summary="Request password reset")
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    svc: AuthService = Depends(get_auth_service),
):
    await _enforce_auth_rate_limit(request, "forgot_password")
    await svc.forgot_password(payload.email)
    return {"detail": "If the email exists, a password reset link has been sent"}


@router.post("/reset-password",
    summary="Reset password with token")
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    svc: AuthService = Depends(get_auth_service),
):
    await _enforce_auth_rate_limit(request, "reset_password")
    await svc.reset_password(payload.token, payload.new_password)
    return {"detail": "Password has been reset successfully"}


@router.post("/verify-email",
    summary="Verify email address")
async def verify_email(
    request: Request,
    payload: VerifyEmailRequest,
    svc: AuthService = Depends(get_auth_service),
):
    await _enforce_auth_rate_limit(request, "verify_email")
    await svc.verify_email(payload.token)
    return {"detail": "Email verified successfully"}


@router.post("/resend-verification",
    summary="Resend the email verification link")
async def resend_verification(
    request: Request,
    current_user: User = Depends(get_current_user),
    svc: AuthService = Depends(get_auth_service),
):
    # Declared as a static path, and there is no parameterised sibling under
    # /auth, so there is no ordering hazard here (contrast /oauth/exchange,
    # which must stay above /oauth/{provider}).
    await _enforce_auth_rate_limit(request, "resend_verification")
    if not await svc.resend_verification(current_user):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery is not configured on this server. Contact an administrator.",
        )
    return {"detail": "If your address is unverified, a new verification link has been sent"}


@router.get("/me", response_model=UserResponse,
    summary="Get current user profile")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/providers",
    summary="List SSO providers")
async def list_providers():
    return {"providers": SSOProviderRegistry.list_providers()}


@router.post("/oauth/exchange", response_model=TokenWithUser,
    summary="Exchange OAuth handoff code",
    description="One-time exchange of the OAuth callback handoff code for a token pair. Also sets the "
                "auth cookies so the client has a full session immediately — no separate refresh hop. "
                "Returns the user alongside the tokens so the login page can skip a follow-up /auth/me.")
async def oauth_exchange(
    request: Request,
    response: Response,
    payload: OAuthExchangeRequest,
    svc: AuthService = Depends(get_auth_service),
):
    await _enforce_auth_rate_limit(request, "oauth_exchange")
    # MUST be declared before /oauth/{provider}: Starlette matches routes in
    # registration order, so a parameterized route would otherwise swallow the
    # static "exchange" path and the one-time handoff could never be redeemed.
    refresh_token = await svc.exchange_oauth_handoff(payload.code)
    # Mint an access token from the refresh token so the session cookies are
    # complete without another round trip. The one-time code is already consumed
    # server-side, so establishing the session here avoids a second request whose
    # failure would strand the user mid-login.
    token_payload = decode_token(refresh_token)
    user_id = token_payload.get("sub")
    if not user_id or token_payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OAuth handoff")
    user = await svc.user_repo.get(int(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OAuth user not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    access_token = create_access_token(data={"sub": str(user_id)})
    _set_auth_cookies(response, access_token, refresh_token)
    return TokenWithUser(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/oauth/{provider}",
    summary="Initiate OAuth flow",
    description="Returns the authorization URL for the given SSO provider (Google, GitHub, etc.).")
async def initiate_oauth(request: Request, provider: str, svc: AuthService = Depends(get_auth_service)):
    await _enforce_auth_rate_limit(request, "oauth_callback")
    auth_url, state = await svc.oauth_init(provider)
    return {"authorization_url": auth_url, "state": state}


@router.get("/oauth/{provider}/callback",
    summary="Complete OAuth callback",
    description="Exchange the OAuth authorization code for a JWT token pair, then redirect to frontend.")
async def oauth_callback(
    request: Request,
    provider: str,
    code: str,
    state: str,
    svc: AuthService = Depends(get_auth_service),
):
    await _enforce_auth_rate_limit(request, "oauth_callback")
    tokens = await svc.oauth_callback(provider, code, state)
    # The refresh token is never put in the redirect URL (it would leak through
    # access logs and Referer headers). Instead a short-lived one-time handoff
    # code is passed; the login page exchanges it for the token pair.
    if not tokens.refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OAuth login failed")
    handoff = await svc.create_oauth_handoff(tokens.refresh_token)
    redirect_url = f"{settings.FRONTEND_URL}/login?code={handoff}"
    return RedirectResponse(url=redirect_url, status_code=302)


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str | None) -> None:
    is_prod = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="access_token",
        value=access_token,
        # Deliberately longer than ACCESS_TOKEN_EXPIRE_MINUTES: the browser keeps
        # presenting the expired access token, the API answers 401, and the
        # client swaps it using the refresh cookie. Tying this to the access
        # token's own TTL would log every user out every hour.
        max_age=settings.ACCESS_COOKIE_MAX_AGE,
        path="/",
        secure=is_prod,
        httponly=True,
        samesite="lax",
    )
    if refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            # Validated against REFRESH_TOKEN_EXPIRE_DAYS in Settings, so the
            # cookie can never outlive the token it carries and start replaying
            # a dead credential.
            max_age=settings.REFRESH_COOKIE_MAX_AGE,
            path="/",
            secure=is_prod,
            httponly=True,
            samesite="lax",
        )


def _clear_auth_cookies(response: Response) -> None:
    """Delete both auth cookies on a response.

    The only thing that can clear them: both are httpOnly, so `document.cookie`
    can neither read nor delete them.
    """
    is_prod = settings.ENVIRONMENT == "production"
    for key in ("access_token", "refresh_token"):
        response.delete_cookie(key, path="/", secure=is_prod, httponly=True, samesite="lax")


def _refresh_rejected_response() -> JSONResponse:
    """401 for a dead refresh token, carrying the cookie deletion.

    Built by hand rather than raised, because raising an AppError/HTTPException
    discards the injected `Response` and any headers set on it — which is
    precisely the header that has to reach the browser.
    """
    resp = JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Refresh token is no longer valid."},
    )
    _clear_auth_cookies(resp)
    return resp


# --- Auth-path rate limits -------------------------------------------------
# The global middleware only applies a blanket per-IP-per-path bucket sized for
# normal API traffic (60 burst / 1 per sec). Credential endpoints need much
# tighter budgets: a login bucket that refills at 1/s permits thousands of
# guesses per hour, and forgot-password is an unauthenticated mail cannon.
_AUTH_LIMITS = {
    "login": (10, 1.0 / 10.0),          # 10 attempts, refilling 1 per 10s
    "forgot_password": (5, 1.0 / 600.0),  # 5 per 10 min
    "reset_password": (10, 1.0 / 300.0),  # 10 per 5 min
    "verify_email": (20, 1.0 / 60.0),     # 20 per minute
    # Authenticated, but it is still a mail cannon: a shared NAT could otherwise
    # let one caller flood a mailbox.
    "resend_verification": (5, 1.0 / 300.0),  # 5 per 5 min
    "refresh": (60, 1.0 / 2.0),           # concurrent 401 storms are normal
    "oauth_exchange": (20, 1.0 / 30.0),
    "oauth_callback": (30, 1.0 / 10.0),
}


async def _enforce_auth_rate_limit(request: Request, action: str) -> None:
    capacity, refill = _AUTH_LIMITS[action]
    key = f"rl:auth:{action}:{get_client_ip(request)}"
    if await check_rate_limit(key, capacity=capacity, refill_rate_per_sec=refill):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please wait and try again.",
        )
