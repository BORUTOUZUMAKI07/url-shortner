from fastapi import status


class TestProfileRoutes:
    async def test_change_password(self, client):
        resp = await client.put("/api/v1/profile/password", json={
            "current_password": "testpass123",
            "new_password": "NewStrongPass1!",
        })
        assert resp.status_code == status.HTTP_200_OK
        assert "changed" in resp.json()["detail"].lower()

    async def test_change_password_wrong_current(self, client):
        """A wrong current password is a 400, not a 401. Do not "fix" this.

        This asserted 401 for a long time, and the status code was actively
        harmful rather than merely loose. The caller here is *already
        authenticated* — the request carries their valid access token — so 401
        is a false statement about the session. Clients correctly read 401 as
        "re-authenticate", and the frontend's fetch wrapper did exactly that:
        it refreshed the token, re-sent the request with the same wrong
        password, and then surfaced the generic "Session expired. Please login
        again." instead of naming the field that was wrong. It also wrote two
        `password_change_failed` audit rows for one user action.

        The fix is a distinct error (`IncorrectCurrentPassword`, a
        `BadRequestError`) rather than reusing `InvalidCredentials`, which stays
        a 401 because login genuinely has no session yet.

        The message matters as much as the code: it must name the field.
        """
        resp = await client.put("/api/v1/profile/password", json={
            "current_password": "wrongpassword",
            "new_password": "NewStrongPass1!",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["detail"] == "Current password is incorrect."

    async def test_wrong_current_password_does_not_revoke_sessions(self, client, test_user):
        """The 401 also implied the session was dead, so it must not act like it.

        A rejected attempt changes nothing: not the password, and not the
        session. Only a *successful* change revokes the refresh family, so a
        user who mistypes their current password is not signed out of their own
        account — and an attacker cannot use failed guesses to invalidate
        someone else's session.
        """
        assert test_user.password_hash, "fixture must have a password to change"
        resp = await client.put("/api/v1/profile/password", json={
            "current_password": "wrongpassword",
            "new_password": "NewStrongPass1!",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

        # The stored hash is untouched: the new password does not work.
        login = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "NewStrongPass1!",
        })
        assert login.status_code == status.HTTP_401_UNAUTHORIZED

        # And the original still does.
        login = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "testpass123",
        })
        assert login.status_code == status.HTTP_200_OK

    async def test_change_password_short_new(self, client):
        resp = await client.put("/api/v1/profile/password", json={
            "current_password": "testpass123",
            "new_password": "short",
        })
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_change_email(self, client):
        resp = await client.put("/api/v1/profile/email", json={
            "new_email": "newemail@example.com",
            "current_password": "testpass123",
        })
        assert resp.status_code == status.HTTP_200_OK
        assert "changed" in resp.json()["detail"].lower()

    async def test_change_email_wrong_password(self, client):
        """400, not 401 — same reasoning as test_change_password_wrong_current.

        `change_email` raised the same `InvalidCredentials` on a bad
        `current_password`, so it suffered the identical fault: the client saw
        401 on an authenticated request, refreshed, retried with the same wrong
        password, and reported a session problem instead of a wrong field.
        """
        resp = await client.put("/api/v1/profile/email", json={
            "new_email": "newemail@example.com",
            "current_password": "wrongpassword",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["detail"] == "Current password is incorrect."

    async def test_change_email_already_exists(self, client, test_user):
        resp = await client.put("/api/v1/profile/email", json={
            "new_email": test_user.email,
            "current_password": "testpass123",
        })
        assert resp.status_code == status.HTTP_409_CONFLICT

    async def test_upload_avatar(self, client):
        resp = await client.post("/api/v1/profile/avatar", json={
            "avatar": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        })
        assert resp.status_code == status.HTTP_200_OK
        assert "updated" in resp.json()["detail"].lower()
        assert resp.json()["avatar_url"] is not None

    async def test_upload_avatar_empty(self, client):
        resp = await client.post("/api/v1/profile/avatar", json={
            "avatar": "",
        })
        assert resp.status_code == status.HTTP_200_OK

    async def test_no_auth(self, app):
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.put("/api/v1/profile/password", json={
                "current_password": "testpass123",
                "new_password": "NewStrongPass1!",
            })
            assert resp.status_code == status.HTTP_401_UNAUTHORIZED
