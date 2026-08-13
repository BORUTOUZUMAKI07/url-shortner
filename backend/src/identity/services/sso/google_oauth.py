import logging
from urllib.parse import urlencode

import httpx

from src.shared.core.config import settings

logger = logging.getLogger("url-shortener")


class GoogleOAuthProvider:
    name = "google"
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://www.googleapis.com/oauth2/v4/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    def is_configured(self) -> bool:
        return bool(settings.GOOGLE_OAUTH_CLIENT_ID)

    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "consent select_account",
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict | None:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    self.TOKEN_URL,
                    data={
                        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
                    },
                    timeout=10.0,
                )
                if resp.status_code != 200:
                    logger.error(f"Google token exchange failed: {resp.status_code} - {resp.text}")
                    return None
                return resp.json()  # type: ignore[no-any-return]
            except Exception as e:
                logger.error(f"Google token exchange error: {e}")
                return None

    async def get_user_info(self, access_token: str) -> dict | None:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    self.USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10.0,
                )
                if resp.status_code != 200:
                    logger.error(f"Google userinfo failed: {resp.status_code} - {resp.text}")
                    return None
                data = resp.json()
                return {
                    "id": data.get("id"),
                    "email": data.get("email"),
                    "name": data.get("name"),
                    "picture": data.get("picture"),
                    "verified_email": data.get("verified_email", False),
                }
            except Exception as e:
                logger.error(f"Google userinfo error: {e}")
                return None

    async def authenticate(self, code: str) -> dict | None:
        token_resp = await self.exchange_code(code)
        if not token_resp or not token_resp.get("access_token"):
            return None
        return await self.get_user_info(token_resp["access_token"])
