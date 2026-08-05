from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials

from src.core.config import settings
from src.core.deps import bearer_scheme, get_auth_service, get_current_user
from src.models.user import User
from src.schemas.user import (
    ForgotPasswordRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    VerifyEmailRequest,
)
from src.services.auth_service import AuthService
from src.services.sso import SSOProviderRegistry

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
async def refresh(response: Response, payload: RefreshTokenRequest, svc: AuthService = Depends(get_auth_service)):
    token = await svc.refresh(payload.refresh_token)
    _set_auth_cookies(response, token.access_token, token.refresh_token)
    return token


@router.post("/logout",
    summary="Logout",
    description="Blacklists the current access token and clears auth cookies.")
async def logout(
    response: Response,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    svc: AuthService = Depends(get_auth_service),
):
    await svc.logout(credentials.credentials)
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
    redirect_url = f"{settings.FRONTEND_URL}/login?access_token={tokens.access_token}&refresh_token={tokens.refresh_token}"
    return RedirectResponse(url=redirect_url, status_code=302)


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
