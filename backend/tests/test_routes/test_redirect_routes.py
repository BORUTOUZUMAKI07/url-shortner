from fastapi import status

from src.shared.core.config import settings


class TestRedirectRoutes:
    async def test_redirect_active_url(self, client, test_url):
        resp = await client.get(f"/{test_url.short_code}", follow_redirects=False)
        assert resp.status_code == status.HTTP_302_FOUND
        assert resp.headers["location"] == test_url.original_url

    async def test_redirect_not_found(self, client):
        resp = await client.get("/nonexistent123", follow_redirects=False)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    async def test_redirect_with_follow(self, client, test_url):
        resp = await client.get(f"/{test_url.short_code}", follow_redirects=False)
        assert resp.status_code == status.HTTP_302_FOUND
        assert resp.headers["location"] == test_url.original_url

    async def test_post_to_nonexistent_short_code(self, client):
        resp = await client.post("/nonexistent", data={"pwd": "test"}, follow_redirects=False)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_health(self, client):
        resp = await client.get("/health", follow_redirects=False)
        assert resp.status_code in (200, 503)

    async def test_post_password_unlock_from_frontend_origin_is_allowed(self, client, test_url):
        """The frontend proxies ``/{short_code}`` to the backend (next.config.ts)
        and the app copies short links at ``window.location.origin``, so the
        unlock POST arrives with a frontend Referer. Before the guard accepted
        ``FRONTEND_URL`` that was a blanket 404 on the canonical link."""
        resp = await client.post(
            f"/{test_url.short_code}",
            data={"pwd": "anything"},
            headers={"Referer": f"{settings.FRONTEND_URL}/{test_url.short_code}"},
            follow_redirects=False,
        )
        assert resp.status_code != status.HTTP_404_NOT_FOUND

    async def test_post_password_unlock_from_foreign_origin_is_rejected(self, client, test_url):
        resp = await client.post(
            f"/{test_url.short_code}",
            data={"pwd": "anything"},
            headers={"Referer": "https://attacker.invalid/"},
            follow_redirects=False,
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
