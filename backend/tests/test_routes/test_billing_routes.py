from fastapi import status


class TestBillingRoutes:
    async def test_upgrade_to_premium(self, client):
        resp = await client.post("/api/v1/billing/upgrade", json={
            "plan": "premium",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["plan"] == "premium"
        assert "upgraded" in data["detail"].lower()

    async def test_upgrade_to_enterprise(self, client):
        resp = await client.post("/api/v1/billing/upgrade", json={
            "plan": "enterprise",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["plan"] == "enterprise"

    async def test_upgrade_same_plan(self, client):
        resp = await client.post("/api/v1/billing/upgrade", json={
            "plan": "free",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["plan"] == "free"
        assert "already" in data["detail"].lower()

    async def test_upgrade_invalid_plan(self, client):
        resp = await client.post("/api/v1/billing/upgrade", json={
            "plan": "ultra",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid plan" in resp.json()["detail"].lower()

    async def test_upgrade_no_auth(self, app):
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/v1/billing/upgrade", json={
                "plan": "premium",
            })
            assert resp.status_code == status.HTTP_401_UNAUTHORIZED
