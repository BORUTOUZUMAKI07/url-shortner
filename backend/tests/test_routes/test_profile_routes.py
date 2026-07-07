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
        resp = await client.put("/api/v1/profile/password", json={
            "current_password": "wrongpassword",
            "new_password": "NewStrongPass1!",
        })
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_change_password_short_new(self, client):
        resp = await client.put("/api/v1/profile/password", json={
            "current_password": "testpass123",
            "new_password": "short",
        })
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_change_email(self, client):
        resp = await client.put("/api/v1/profile/email", json={
            "new_email": "newemail@example.com",
            "current_password": "testpass123",
        })
        assert resp.status_code == status.HTTP_200_OK
        assert "changed" in resp.json()["detail"].lower()

    async def test_change_email_wrong_password(self, client):
        resp = await client.put("/api/v1/profile/email", json={
            "new_email": "newemail@example.com",
            "current_password": "wrongpassword",
        })
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

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
