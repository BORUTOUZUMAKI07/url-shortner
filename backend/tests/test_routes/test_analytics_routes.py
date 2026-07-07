from unittest.mock import AsyncMock, patch

from fastapi import status


class TestAnalyticsRoutes:
    async def test_get_summary(self, client, test_url):
        resp = await client.get(f"/api/v1/analytics/{test_url.short_code}/summary")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["short_code"] == test_url.short_code
        assert "total_clicks" in data
        assert "unique_clicks" in data
        assert data["total_clicks"] == 0

    async def test_get_summary_not_found(self, client):
        resp = await client.get("/api/v1/analytics/nonexistent/summary")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    @patch("src.services.analytics_service.ClickEvent.aggregate")
    async def test_get_timeseries(self, mock_aggregate, client, test_url):
        mock_aggregate.return_value.to_list = AsyncMock(return_value=[])
        resp = await client.get(f"/api/v1/analytics/{test_url.short_code}/timeseries?days=7")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["short_code"] == test_url.short_code
        assert "data" in data
        assert data["days"] == 7

    @patch("src.services.analytics_service.ClickEvent.aggregate")
    async def test_get_timeseries_default_days(self, mock_aggregate, client, test_url):
        mock_aggregate.return_value.to_list = AsyncMock(return_value=[])
        resp = await client.get(f"/api/v1/analytics/{test_url.short_code}/timeseries")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["days"] == 7

    @patch("src.services.analytics_service.ClickEvent.aggregate")
    async def test_get_timeseries_custom_days(self, mock_aggregate, client, test_url):
        mock_aggregate.return_value.to_list = AsyncMock(return_value=[])
        resp = await client.get(f"/api/v1/analytics/{test_url.short_code}/timeseries?days=30")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["days"] == 30

    @patch("src.services.analytics_service.ClickEvent.aggregate")
    async def test_get_timeseries_invalid_days(self, mock_aggregate, client, test_url):
        resp = await client.get(f"/api/v1/analytics/{test_url.short_code}/timeseries?days=999")
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("src.services.analytics_service.ClickEvent.aggregate")
    async def test_get_device_breakdown(self, mock_aggregate, client, test_url):
        mock_aggregate.return_value.to_list = AsyncMock(return_value=[])
        resp = await client.get(f"/api/v1/analytics/{test_url.short_code}/devices")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["short_code"] == test_url.short_code
        assert "browsers" in data
        assert "os" in data
        assert "devices" in data
        assert "geo" in data

    @patch("src.services.analytics_service.ClickEvent.aggregate")
    async def test_get_utm_breakdown(self, mock_aggregate, client, test_url):
        mock_aggregate.return_value.to_list = AsyncMock(return_value=[])
        resp = await client.get(f"/api/v1/analytics/{test_url.short_code}/utm")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["short_code"] == test_url.short_code
        assert "data" in data

    @patch("src.services.analytics_service.ClickEvent.aggregate")
    async def test_get_referer_breakdown(self, mock_aggregate, client, test_url):
        mock_aggregate.return_value.to_list = AsyncMock(return_value=[])
        resp = await client.get(f"/api/v1/analytics/{test_url.short_code}/referrers")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["short_code"] == test_url.short_code
        assert "data" in data

    async def test_no_auth(self, app, test_url):
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(f"/api/v1/analytics/{test_url.short_code}/summary")
            assert resp.status_code == status.HTTP_401_UNAUTHORIZED
