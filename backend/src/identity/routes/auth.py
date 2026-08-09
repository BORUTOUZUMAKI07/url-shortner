from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials

from src.identity.models.user import User
from src.identity.schemas.user import (
    ForgotPasswordRequest,
    OAuthExchangeRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    VerifyEmailRequest,
)
from src.identity.services.auth_service import AuthService
from src.identity.services.sso import SSOProviderRegistry
from src.shared.core.config import settings
from src.shared.core.deps import bearer_scheme, get_auth_service, get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    response_description="The newly created user (password excluded)")
async def register(payload: UserCreate, svc: AuthService = Depends(get_auth_service)):
    return await svc.register(payload.email, payload.password)


@router.post("/login", response_model=Token,
    summary="Login",
    description="Authenticate with email and password to receive access and refresh tokens.")
async def login(response: Response, payload: UserLogin, svc: AuthService = Depends(get_auth_service)):
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
    refresh_token = payload.refresh_token if payload and payload.refresh_token else request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")
    token = await svc.refresh(refresh_token)
    _set_auth_cookies(response, token.access_token, token.refresh_token)
    return token


@router.post("/logout",
    summary="Logout",
    description="Blacklists the current access token and clears auth cookies.")
async def logout(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    svc: AuthService = Depends(get_auth_service),
):
    await svc.logout(credentials.credentials)
    refresh_cookie = request.cookies.get("refresh_token")
    if refresh_cookie:
        try:
            await svc.logout(refresh_cookie)
        except Exception:
            pass
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    return {"detail": "Successfully logged out"}


@router.post("/forgot-password",
    summary="Request password reset")
async def forgot_password(payload: ForgotPasswordRequest, svc: AuthService = Depends(get_auth_service)):
    await svc.forgot_password(payload.email)
    return {"detail": "If the email exists, a password reset link has been sent"}


@router.post("/reset-password",
    summary="Reset password with token")
async def reset_password(payload: ResetPasswordRequest, svc: AuthService = Depends(get_auth_service)):
    await svc.reset_password(payload.token, payload.new_password)
    return {"detail": "Password has been reset successfully"}


@router.post("/verify-email",
    summary="Verify email address")
async def verify_email(payload: VerifyEmailRequest, svc: AuthService = Depends(get_auth_service)):
    await svc.verify_email(payload.token)
    return {"detail": "Email verified successfully"}


@router.get("/me", response_model=UserResponse,
    summary="Get current user profile")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/providers",
    summary="List SSO providers")
async def list_providers():
    return {"providers": SSOProviderRegistry.list_providers()}


@router.post("/oauth/{provider}",
    summary="Initiate OAuth flow",
    description="Returns the authorization URL for the given SSO provider (Google, GitHub, etc.).")
async def initiate_oauth(provider: str, svc: AuthService = Depends(get_auth_service)):
    auth_url, state = await svc.oauth_init(provider)
    return {"authorization_url": auth_url, "state": state}


@router.get("/oauth/{provider}/callback",
    summary="Complete OAuth callback",
    description="Exchange the OAuth authorization code for a JWT token pair, then redirect to frontend.")
async def oauth_callback(provider: str, code: str, state: str, svc: AuthService = Depends(get_auth_service)):
    tokens = await svc.oauth_callback(provider, code, state)
    # The refresh token is never put in the redirect URL (it would leak through
    # access logs and Referer headers). Instead a short-lived one-time handoff
    # code is passed; the login page exchanges it for the token pair.
    if not tokens.refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OAuth login failed")
    handoff = await svc.create_oauth_handoff(tokens.refresh_token)
    redirect_url = f"{settings.FRONTEND_URL}/login?code={handoff}"
    return RedirectResponse(url=redirect_url, status_code=302)


@router.post("/oauth/exchange",
    summary="Exchange OAuth handoff code",
    description="One-time exchange of the OAuth callback handoff code for a refresh token.")
async def oauth_exchange(payload: OAuthExchangeRequest, svc: AuthService = Depends(get_auth_service)):
    refresh_token = await svc.exchange_oauth_handoff(payload.code)
    return {"refresh_token": refresh_token}


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str | None) -> None:
    is_prod = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=604800,
        path="/",
        secure=is_prod,
        httponly=True,
        samesite="lax",
    )
    if refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            max_age=2592000,
            path="/",
            secure=is_prod,
            httponly=True,
            samesite="lax",
        )
