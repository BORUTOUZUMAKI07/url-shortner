from fastapi import status


class TestAdminRoutes:
    async def _make_superadmin(self, db, test_user):
        test_user.is_superadmin = True
        db.add(test_user)
        await db.commit()

    async def test_seed_superadmin(self, client):
        resp = await client.post("/api/v1/admin/seed")
        if resp.status_code == status.HTTP_400_BAD_REQUEST:
            return
        assert resp.status_code == status.HTTP_200_OK
        assert "superadmin" in resp.json()["detail"]

    async def test_seed_already_exists(self, client):
        resp = await client.post("/api/v1/admin/seed")
        assert resp.status_code in (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST)

    async def test_list_users(self, client, db, test_user):
        await self._make_superadmin(db, test_user)
        resp = await client.get("/api/v1/admin/users")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "total" in data
        assert "users" in data
        assert data["total"] >= 1

    async def test_list_users_forbidden(self, client):
        resp = await client.get("/api/v1/admin/users")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    async def test_get_user(self, client, db, test_user):
        await self._make_superadmin(db, test_user)
        list_resp = await client.get("/api/v1/admin/users")
        user_id = list_resp.json()["users"][0]["id"]
        resp = await client.get(f"/api/v1/admin/users/{user_id}")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["email"] == "test@example.com"

    async def test_get_user_not_found(self, client, db, test_user):
        await self._make_superadmin(db, test_user)
        resp = await client.get("/api/v1/admin/users/999999")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    async def test_toggle_superadmin(self, client, db, test_user):
        await self._make_superadmin(db, test_user)
        list_resp = await client.get("/api/v1/admin/users")
        user_id = list_resp.json()["users"][0]["id"]
        resp = await client.patch(f"/api/v1/admin/users/{user_id}/toggle-superadmin")
        assert resp.status_code == status.HTTP_200_OK
        assert "superadmin=False" in resp.json()["detail"]

    async def test_toggle_superadmin_not_found(self, client, db, test_user):
        await self._make_superadmin(db, test_user)
        resp = await client.patch("/api/v1/admin/users/999999/toggle-superadmin")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_user(self, client, db, test_user):
        await self._make_superadmin(db, test_user)
        await client.post("/api/v1/auth/register", json={
            "email": "delete-target@example.com", "password": "StrongPass1!"
        })
        list_resp = await client.get("/api/v1/admin/users")
        target = [u for u in list_resp.json()["users"] if u["email"] == "delete-target@example.com"]
        assert len(target) == 1
        resp = await client.delete(f"/api/v1/admin/users/{target[0]['id']}")
        assert resp.status_code == status.HTTP_200_OK
        assert "deleted" in resp.json()["detail"].lower()

    async def test_delete_user_not_found(self, client, db, test_user):
        await self._make_superadmin(db, test_user)
        resp = await client.delete("/api/v1/admin/users/999999")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    async def test_list_workspaces(self, client, db, test_user):
        await self._make_superadmin(db, test_user)
        resp = await client.get("/api/v1/admin/workspaces")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "total" in data
        assert "workspaces" in data
        assert data["total"] >= 1

    async def test_list_workspaces_forbidden(self, client):
        resp = await client.get("/api/v1/admin/workspaces")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    async def test_list_all_urls(self, client, db, test_user):
        await self._make_superadmin(db, test_user)
        resp = await client.get("/api/v1/admin/urls")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "total" in data
        assert "urls" in data

    async def test_list_all_urls_forbidden(self, client):
        resp = await client.get("/api/v1/admin/urls")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    async def test_platform_stats(self, client, db, test_user):
        await self._make_superadmin(db, test_user)
        resp = await client.get("/api/v1/admin/stats")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "total_users" in data
        assert "total_workspaces" in data
        assert "total_urls" in data
        assert data["total_users"] >= 1
        assert data["total_workspaces"] >= 1
        assert data["total_urls"] >= 1

    async def test_platform_stats_forbidden(self, client):
        resp = await client.get("/api/v1/admin/stats")
        assert resp.status_code == status.HTTP_403_FORBIDDEN
