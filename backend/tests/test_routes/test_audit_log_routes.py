from fastapi import status


class TestAuditLogRoutes:
    async def test_get_workspace_logs(self, client, test_workspace):
        resp = await client.get(f"/api/v1/audit-logs/workspace/{test_workspace.id}")
        assert resp.status_code == status.HTTP_200_OK
        assert isinstance(resp.json(), list)

    async def test_get_workspace_logs_with_pagination(self, client, test_workspace):
        resp = await client.get(f"/api/v1/audit-logs/workspace/{test_workspace.id}?skip=0&limit=10")
        assert resp.status_code == status.HTTP_200_OK
        assert isinstance(resp.json(), list)

    async def test_get_workspace_logs_not_found(self, client):
        resp = await client.get("/api/v1/audit-logs/workspace/999999")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_resource_logs(self, client, test_url):
        resp = await client.get(f"/api/v1/audit-logs/resource/url/{test_url.id}")
        assert resp.status_code == status.HTTP_200_OK
        assert isinstance(resp.json(), list)

    async def test_get_resource_logs_unknown_type(self, client):
        resp = await client.get("/api/v1/audit-logs/resource/unknown/1")
        assert resp.status_code == status.HTTP_200_OK
        assert isinstance(resp.json(), list)

    async def test_get_actor_logs_own(self, client, test_user):
        resp = await client.get(f"/api/v1/audit-logs/actor/{test_user.id}")
        assert resp.status_code == status.HTTP_200_OK
        assert isinstance(resp.json(), list)

    async def test_get_actor_logs_different_actor(self, client):
        resp = await client.get("/api/v1/audit-logs/actor/999999")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    async def test_no_auth(self, app, test_workspace):
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(f"/api/v1/audit-logs/workspace/{test_workspace.id}")
            assert resp.status_code == status.HTTP_401_UNAUTHORIZED
