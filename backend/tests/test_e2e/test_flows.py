"""Backend E2E flow tests over real HTTP against a real uvicorn process."""
from __future__ import annotations

import os
import secrets

import httpx
import pytest
import pytest_asyncio

if os.environ.get("_USE_TESTCONTAINERS") != "1":
    pytest.skip(
        "Backend E2E tests require Docker testcontainers (--use-testcontainers). "
        "Never run them against the real .env database.",
        allow_module_level=True,
    )

pytestmark = pytest.mark.integration

PASSWORD = "StrongPass1!"


def unique_email() -> str:
    return f"e2e-{secrets.token_hex(6)}@example.com"


@pytest_asyncio.fixture
async def client(server) -> httpx.AsyncClient:
    async with httpx.AsyncClient(base_url=server, timeout=30, follow_redirects=False) as c:
        yield c


async def register_and_login(client: httpx.AsyncClient) -> tuple[str, dict]:
    email = unique_email()
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 201, resp.text
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    token = resp.json()
    assert token["access_token"]
    return email, {"Authorization": f"Bearer {token['access_token']}"}


class TestAuthFlow:
    async def test_register_login_me(self, client):
        email, headers = await register_and_login(client)
        resp = await client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == email

    async def test_duplicate_email_is_conflict(self, client):
        email, _ = await register_and_login(client)
        resp = await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
        assert resp.status_code == 409

    async def test_unauthenticated_workspace_list_is_401(self, client):
        resp = await client.get("/api/v1/workspaces")
        assert resp.status_code == 401


class TestURLLifecycle:
    async def test_create_list_get_and_redirect(self, client):
        _, headers = await register_and_login(client)

        ws_resp = await client.get("/api/v1/workspaces", headers=headers)
        assert ws_resp.status_code == 200
        workspaces = ws_resp.json()
        assert len(workspaces) == 1  # register() auto-creates the default workspace
        workspace_id = workspaces[0]["id"]

        original = "https://example.com/e2e-destination"
        create_resp = await client.post(
            "/api/v1/urls",
            json={"original_url": original, "workspace_id": workspace_id},
            headers=headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        created = create_resp.json()
        short_code = created["short_code"]
        assert short_code

        list_resp = await client.get("/api/v1/urls", headers=headers)
        assert list_resp.status_code == 200
        assert any(item["id"] == created["id"] for item in list_resp.json()["items"])

        detail_resp = await client.get(f"/api/v1/urls/{created['id']}", headers=headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["original_url"] == original

        # The public short link 302/307s to the original over the wire.
        redirect_resp = await client.get(f"/{short_code}")
        assert redirect_resp.status_code in (301, 302, 307, 308)
        assert redirect_resp.headers["location"] == original

    async def test_create_url_requires_auth(self, client):
        resp = await client.post(
            "/api/v1/urls",
            json={"original_url": "https://example.com/no-auth", "workspace_id": 1},
        )
        assert resp.status_code == 401


class TestAPIKeys:
    async def test_create_key_and_authenticate_with_it(self, client):
        _, headers = await register_and_login(client)

        create_resp = await client.post("/api/v1/api-keys", json={"name": "ci"}, headers=headers)
        assert create_resp.status_code == 201, create_resp.text
        api_key = create_resp.json()["key"]
        assert api_key.startswith("lf_")

        resp = await client.get("/api/v1/urls", headers={"Authorization": f"Bearer {api_key}"})
        assert resp.status_code == 200
        assert "items" in resp.json()


class TestWebhooks:
    async def test_create_and_list_webhook(self, client):
        _, headers = await register_and_login(client)

        ws_resp = await client.get("/api/v1/workspaces", headers=headers)
        workspace_id = ws_resp.json()[0]["id"]

        create_resp = await client.post(
            f"/api/v1/webhooks/workspace/{workspace_id}",
            json={"url": "https://example.com/callback", "events": ["click"], "secret": f"whsec_{secrets.token_hex(8)}"},
            headers=headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        webhook_id = create_resp.json()["id"]

        list_resp = await client.get(f"/api/v1/webhooks/workspace/{workspace_id}", headers=headers)
        assert list_resp.status_code == 200
        assert any(hook["id"] == webhook_id for hook in list_resp.json())
