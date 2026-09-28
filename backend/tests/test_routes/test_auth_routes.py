from fastapi import status


class TestAuthRoutes:
    async def test_register(self, client):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "newuser@example.com",
            "password": "StrongPass1!",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["email"] == "newuser@example.com"
        assert "id" in data
        assert "password" not in data

    async def test_register_duplicate(self, client, test_user):
        resp = await client.post("/api/v1/auth/register", json={
            "email": test_user.email,
            "password": "StrongPass1!",
        })
        assert resp.status_code == status.HTTP_409_CONFLICT

    async def test_login_success(self, client, test_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "testpass123",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client, test_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "wrongpass",
        })
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_login_nonexistent_user(self, client):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "noone@example.com",
            "password": "testpass123",
        })
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_me_authenticated(self, client, auth_headers, test_user):
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["email"] == test_user.email

    async def test_get_me_unauthenticated(self, unauth_client):
        resp = await unauth_client.get("/api/v1/auth/me")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_forgot_password(self, client):
        resp = await client.post("/api/v1/auth/forgot-password", json={
            "email": "test@example.com",
        })
        assert resp.status_code == status.HTTP_200_OK
        assert "sent" in resp.json()["detail"].lower()

    async def test_refresh_invalid_token(self, client):
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid-token",
        })
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_rejected_refresh_deletes_the_auth_cookies(self, client):
        """A dead refresh cookie must stop being replayed.

        The refresh cookie is httpOnly, so nothing client-side can remove it —
        JS can neither read nor delete it. Before this fix a rejected refresh
        raised, which discarded the injected `Response` and therefore the delete
        headers, and the cookie survived for the rest of its max_age (7 days by
        default).

        Two consequences, both silent: every subsequent request replayed a
        credential known to be dead, and each replay consumed the per-IP
        `refresh` rate-limit budget (1 per 10s refill), so a stuck client could
        throttle the user's own next sign-in.
        """
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid-token",
        })
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

        # httponly is required on the delete, otherwise the browser can treat it
        # as a different cookie from the one that was set and ignore it.
        set_cookies = resp.headers.get_list("set-cookie")
        deletes = [c for c in set_cookies if c.split("=")[0].strip() in ("access_token", "refresh_token")]
        assert len(deletes) == 2, f"expected both auth cookies cleared, got: {set_cookies}"
        for c in deletes:
            name = c.split("=")[0].strip()
            assert 'Max-Age=0' in c or 'max-age=0' in c.lower(), f"{name} not expired: {c}"
            assert "HttpOnly" in c, f"{name} delete missing HttpOnly: {c}"
            assert "Path=/" in c, f"{name} delete missing path scope: {c}"

    async def test_rejected_refresh_explains_itself(self, client):
        """The old message was "Missing refresh token" for every failure mode.

        A token that is present but expired, revoked or replayed is a different
        situation from one that was never sent, and the client shows this text
        to the user.
        """
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid-token"})
        assert resp.json()["detail"] == "Refresh token is no longer valid."

    async def test_missing_refresh_token_also_clears_cookies(self, client):
        """The no-token case reaches the same handler and must behave the same.

        It used to raise HTTPException directly, bypassing the cookie deletion
        entirely — so the branch right above the one that mattered was the one
        that leaked.
        """
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        set_cookies = resp.headers.get_list("set-cookie")
        assert any(c.startswith("refresh_token=") for c in set_cookies)

    async def test_oauth_exchange_not_shadowed_by_provider_route(self, client):
        # Regression: /oauth/{provider} was registered BEFORE /oauth/exchange,
        # and Starlette matches in registration order — so POST
        # /auth/oauth/exchange resolved to initiate_oauth("exchange") and every
        # handoff exchange 400'd with "OAuth provider 'exchange' is not
        # configured", breaking Google/GitHub sign-in. The static route must
        # win: an unknown code should be an InvalidToken (401), not a provider
        # lookup failure.
        resp = await client.post("/api/v1/auth/oauth/exchange", json={"code": "bogus-code"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert "not configured" not in resp.json().get("detail", "").lower()
