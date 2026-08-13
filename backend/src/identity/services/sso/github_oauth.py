from urllib.parse import urlencode

import httpx

from src.shared.core.config import settings


class GitHubOAuthProvider:
    name = "github"
    AUTH_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USERINFO_URL = "https://api.github.com/user"
    EMAILS_URL = "https://api.github.com/user/emails"

    def is_configured(self) -> bool:
        return bool(settings.GITHUB_OAUTH_CLIENT_ID)

    def get_authorization_url(self, state: str, code_challenge: str | None = None) -> str:
        params = {
            "client_id": settings.GITHUB_OAUTH_CLIENT_ID,
            "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
            "scope": "read:user user:email",
            "state": state,
            "prompt": "select_account",
        }
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str | None = None) -> dict | None:
        data = {
            "client_id": settings.GITHUB_OAUTH_CLIENT_ID,
            "client_secret": settings.GITHUB_OAUTH_CLIENT_SECRET,
            "code": code,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.TOKEN_URL,
                data=data,
                headers={"Accept": "application/json"},
                timeout=10.0,
            )
            if resp.status_code != 200:
                return None
            return resp.json()  # type: ignore[no-any-return]

    async def get_user_info(self, access_token: str) -> dict | None:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.USERINFO_URL, headers=headers, timeout=10.0)
            if resp.status_code != 200:
                return None
            data = resp.json()
            email = data.get("email")
            if not email:
                emails_resp = await client.get(self.EMAILS_URL, headers=headers, timeout=10.0)
                if emails_resp.status_code == 200:
                    for e in emails_resp.json():
                        if e.get("primary"):
                            email = e["email"]
                            break
            return {
                "id": str(data.get("id")),
                "email": email,
                "name": data.get("name") or data.get("login"),
                "picture": data.get("avatar_url"),
                "verified_email": email is not None,
            }

    async def authenticate(self, code: str, code_verifier: str | None = None) -> dict | None:
        token_resp = await self.exchange_code(code, code_verifier)
        if not token_resp or not token_resp.get("access_token"):
            return None
        return await self.get_user_info(token_resp["access_token"])
