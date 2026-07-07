from fastapi import status


class TestWebhookRoutes:
    async def test_create_webhook(self, client, test_workspace):
        resp = await client.post(f"/api/v1/webhooks/workspace/{test_workspace.id}", json={
            "url": "https://hooks.example.com/callback",
            "events": ["url.created"],
            "secret": "whsec_1234567890123456",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["workspace_id"] == test_workspace.id
        assert data["url"] == "https://hooks.example.com/callback"
        assert "url.created" in data["events"]
        assert data["is_active"] is True

    async def test_create_webhook_multiple_events(self, client, test_workspace):
        resp = await client.post(f"/api/v1/webhooks/workspace/{test_workspace.id}", json={
            "url": "https://hooks.example.com/callback",
            "events": ["url.created", "url.clicked", "url.deleted"],
            "secret": "whsec_1234567890123456",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert len(data["events"]) == 3
        assert "url.created" in data["events"]
        assert "url.clicked" in data["events"]
        assert "url.deleted" in data["events"]

    async def test_create_webhook_empty_events(self, client, test_workspace):
        resp = await client.post(f"/api/v1/webhooks/workspace/{test_workspace.id}", json={
            "url": "https://hooks.example.com/callback",
            "events": [],
            "secret": "whsec_1234567890123456",
        })
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_create_webhook_short_secret(self, client, test_workspace):
        resp = await client.post(f"/api/v1/webhooks/workspace/{test_workspace.id}", json={
            "url": "https://hooks.example.com/callback",
            "events": ["url.created"],
            "secret": "short",
        })
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_create_webhook_invalid_url(self, client, test_workspace):
        resp = await client.post(f"/api/v1/webhooks/workspace/{test_workspace.id}", json={
            "url": "not-a-url",
            "events": ["url.created"],
            "secret": "whsec_1234567890123456",
        })
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_list_webhooks(self, client, test_workspace):
        await client.post(f"/api/v1/webhooks/workspace/{test_workspace.id}", json={
            "url": "https://hooks.example.com/callback",
            "events": ["url.created"],
            "secret": "whsec_1234567890123456",
        })
        resp = await client.get(f"/api/v1/webhooks/workspace/{test_workspace.id}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert len(data) >= 1

    async def test_get_webhook(self, client, test_workspace):
        create = await client.post(f"/api/v1/webhooks/workspace/{test_workspace.id}", json={
            "url": "https://hooks.example.com/callback",
            "events": ["url.created"],
            "secret": "whsec_1234567890123456",
        })
        wh_id = create.json()["id"]
        resp = await client.get(f"/api/v1/webhooks/{wh_id}/workspace/{test_workspace.id}")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["id"] == wh_id

    async def test_get_webhook_not_found(self, client, test_workspace):
        resp = await client.get(f"/api/v1/webhooks/999999/workspace/{test_workspace.id}")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_webhook_events(self, client, test_workspace):
        create = await client.post(f"/api/v1/webhooks/workspace/{test_workspace.id}", json={
            "url": "https://hooks.example.com/callback",
            "events": ["url.created"],
            "secret": "whsec_1234567890123456",
        })
        wh_id = create.json()["id"]
        resp = await client.put(f"/api/v1/webhooks/{wh_id}/workspace/{test_workspace.id}", json={
            "events": ["url.clicked", "url.deleted"],
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "url.clicked" in data["events"]
        assert "url.deleted" in data["events"]

    async def test_update_webhook_disable(self, client, test_workspace):
        create = await client.post(f"/api/v1/webhooks/workspace/{test_workspace.id}", json={
            "url": "https://hooks.example.com/callback",
            "events": ["url.created"],
            "secret": "whsec_1234567890123456",
        })
        wh_id = create.json()["id"]
        resp = await client.put(f"/api/v1/webhooks/{wh_id}/workspace/{test_workspace.id}", json={
            "is_active": False,
        })
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["is_active"] is False

    async def test_delete_webhook(self, client, test_workspace):
        create = await client.post(f"/api/v1/webhooks/workspace/{test_workspace.id}", json={
            "url": "https://hooks.example.com/callback",
            "events": ["url.created"],
            "secret": "whsec_1234567890123456",
        })
        wh_id = create.json()["id"]
        resp = await client.delete(f"/api/v1/webhooks/{wh_id}/workspace/{test_workspace.id}")
        assert resp.status_code == status.HTTP_200_OK
        assert "deleted" in resp.json()["detail"].lower()
        get_resp = await client.get(f"/api/v1/webhooks/{wh_id}/workspace/{test_workspace.id}")
        assert get_resp.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_webhook_not_found(self, client, test_workspace):
        resp = await client.delete(f"/api/v1/webhooks/999999/workspace/{test_workspace.id}")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    async def test_no_auth(self, app, test_workspace):
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(f"/api/v1/webhooks/workspace/{test_workspace.id}")
            assert resp.status_code == status.HTTP_401_UNAUTHORIZED
