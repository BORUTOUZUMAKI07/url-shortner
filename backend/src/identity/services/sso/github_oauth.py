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

            # Always consult /user/emails rather than trusting /user's `email`.
            # /user only returns the address when the user made it public, and
            # GitHub lets an account hold an address it has NOT verified (added
            # via signup, a GitHub App, or an org). Trusting that address let an
            # attacker point their own account at a victim's address and, once
            # we linked OAuth logins by email, take over the victim's account.
            #
            # GitHub is explicit that `email` may be null, so the fallback is
            # mandatory rather than defensive.
            verified_emails: list[str] = []
            primary_verified: str | None = None
            emails_resp = await client.get(self.EMAILS_URL, headers=headers, timeout=10.0)
            if emails_resp.status_code == 200:
                for e in emails_resp.json():
                    address = e.get("email")
                    if not address or not e.get("verified"):
                        continue
                    verified_emails.append(address)
                    if e.get("primary") and primary_verified is None:
                        primary_verified = address

            email = primary_verified
            if email is None and verified_emails:
                # No verified primary - fall back to any verified address rather
                # than rejecting, but never to an unverified one.
                email = verified_emails[0]

            return {
                "id": str(data.get("id")),
                "email": email,
                "name": data.get("name") or data.get("login"),
                "picture": data.get("avatar_url"),
                # Now the provider's own claim, not "an email existed".
                "verified_email": email is not None,
            }

    async def authenticate(self, code: str, code_verifier: str | None = None) -> dict | None:
        token_resp = await self.exchange_code(code, code_verifier)
        if not token_resp or not token_resp.get("access_token"):
            return None
        return await self.get_user_info(token_resp["access_token"])
