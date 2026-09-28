from unittest.mock import AsyncMock, patch

from fastapi import status


class TestAnalyticsRoutes:
    @patch("src.analytics.services.analytics_service.ClickEvent.aggregate")
    async def test_get_summary(self, mock_aggregate, client, test_url):
        # The summary is counted from ClickEvent now, so it can honour `days`
        # like every sibling endpoint. Previously it read the all-time
        # url_analytics_summary row and ignored the period entirely.
        mock_aggregate.return_value.to_list = AsyncMock(
            return_value=[{"total": [{"clicks": 5}], "unique": [{"_id": "1.1.1.1"}, {"_id": "2.2.2.2"}], "last": []}]
        )
        resp = await client.get(f"/api/v1/analytics/{test_url.short_code}/summary")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["short_code"] == test_url.short_code
        assert "total_clicks" in data
        assert "unique_clicks" in data
        assert data["total_clicks"] == 5
        # A true distinct count within the window, not a sum of per-window counts.
        assert data["unique_clicks"] == 2
        assert data["last_clicked_at"] is None

    @patch("src.analytics.services.analytics_service.ClickEvent.aggregate")
    async def test_get_summary_honours_days(self, mock_aggregate, client, test_url):
        """Regression: the route never declared `days`, so FastAPI discarded the
        value the frontend was already sending and these totals were all-time
        while the chart beside them was period-scoped."""
        mock_aggregate.return_value.to_list = AsyncMock(
            return_value=[{"total": [], "unique": [], "last": []}]
        )
        for days in (1, 7, 30):
            resp = await client.get(f"/api/v1/analytics/{test_url.short_code}/summary?days={days}")
            assert resp.status_code == status.HTTP_200_OK
            assert resp.json()["days"] == days

    @patch("src.analytics.services.analytics_service.ClickEvent.aggregate")
    async def test_get_summary_rejects_out_of_range_days(self, mock_aggregate, client, test_url):
        resp = await client.get(f"/api/v1/analytics/{test_url.short_code}/summary?days=0")
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        resp = await client.get(f"/api/v1/analytics/{test_url.short_code}/summary?days=91")
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_get_summary_not_found(self, client):
        resp = await client.get("/api/v1/analytics/nonexistent/summary")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    @patch("src.analytics.services.analytics_service.ClickEvent.aggregate")
    async def test_get_timeseries(self, mock_aggregate, client, test_url):
        mock_aggregate.return_value.to_list = AsyncMock(return_value=[])
        resp = await client.get(f"/api/v1/analytics/{test_url.short_code}/timeseries?days=7")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["short_code"] == test_url.short_code
        assert "data" in data
        assert data["days"] == 7

    @patch("src.analytics.services.analytics_service.ClickEvent.aggregate")
    async def test_get_timeseries_default_days(self, mock_aggregate, client, test_url):
        mock_aggregate.return_value.to_list = AsyncMock(return_value=[])
        resp = await client.get(f"/api/v1/analytics/{test_url.short_code}/timeseries")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["days"] == 7

    @patch("src.analytics.services.analytics_service.ClickEvent.aggregate")
    async def test_get_timeseries_custom_days(self, mock_aggregate, client, test_url):
        mock_aggregate.return_value.to_list = AsyncMock(return_value=[])
        resp = await client.get(f"/api/v1/analytics/{test_url.short_code}/timeseries?days=30")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["days"] == 30

    @patch("src.analytics.services.analytics_service.ClickEvent.aggregate")
    async def test_get_timeseries_invalid_days(self, mock_aggregate, client, test_url):
        resp = await client.get(f"/api/v1/analytics/{test_url.short_code}/timeseries?days=999")
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @patch("src.analytics.services.analytics_service.ClickEvent.aggregate")
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

    @patch("src.analytics.services.analytics_service.ClickEvent.aggregate")
    async def test_get_utm_breakdown(self, mock_aggregate, client, test_url):
        mock_aggregate.return_value.to_list = AsyncMock(return_value=[])
        resp = await client.get(f"/api/v1/analytics/{test_url.short_code}/utm")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["short_code"] == test_url.short_code
        assert "data" in data

    @patch("src.analytics.services.analytics_service.ClickEvent.aggregate")
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
