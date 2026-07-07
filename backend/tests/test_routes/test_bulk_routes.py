from fastapi import status


class TestBulkRoutes:
    async def test_bulk_create_csv(self, client, test_workspace):
        csv_content = b"original_url,custom_alias,expires_at\nhttps://bulk1.example.com,bulk1,2027-01-01T00:00:00\nhttps://bulk2.example.com,bulk2,\nhttps://bulk3.example.com,,\n"
        resp = await client.post(
            f"/api/v1/urls/bulk/create?workspace_id={test_workspace.id}",
            files={"file": ("urls.csv", csv_content, "text/csv")},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["created"] >= 1
        assert len(data["errors"]) == 0
        assert len(data["short_codes"]) >= 1

    async def test_bulk_create_csv_missing_column(self, client, test_workspace):
        csv_content = b"custom_alias\nbulk4\n"
        resp = await client.post(
            f"/api/v1/urls/bulk/create?workspace_id={test_workspace.id}",
            files={"file": ("urls.csv", csv_content, "text/csv")},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["created"] == 0
        assert len(data["errors"]) >= 1
        assert "missing" in data["errors"][0]["error"].lower()

    async def test_bulk_create_csv_reserved_alias(self, client, test_workspace):
        csv_content = b"original_url,custom_alias\nhttps://reserved.example.com,health\n"
        resp = await client.post(
            f"/api/v1/urls/bulk/create?workspace_id={test_workspace.id}",
            files={"file": ("urls.csv", csv_content, "text/csv")},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["created"] == 0
        assert len(data["errors"]) >= 1
        assert "reserved" in data["errors"][0]["error"].lower()

    async def test_bulk_update(self, client, test_workspace):
        csv_content = b"original_url,custom_alias\nhttps://update-me.example.com,update-me\n"
        create_resp = await client.post(
            f"/api/v1/urls/bulk/create?workspace_id={test_workspace.id}",
            files={"file": ("urls.csv", csv_content, "text/csv")},
        )
        short_codes = create_resp.json()["short_codes"]
        list_resp = await client.get(f"/api/v1/urls?workspace_id={test_workspace.id}")
        items = list_resp.json()["items"]
        url_id = [u for u in items if u["short_code"] in short_codes][0]["id"]
        resp = await client.post(
            "/api/v1/urls/bulk/update",
            params={"workspace_id": test_workspace.id, "url_ids": [url_id], "expires_at": "2027-06-15T12:00:00"},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["updated"] == 1

    async def test_bulk_update_no_fields(self, client, test_workspace, test_url):
        resp = await client.post(
            "/api/v1/urls/bulk/update",
            params={"workspace_id": test_workspace.id, "url_ids": [test_url.id]},
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    async def test_bulk_disable(self, client, test_workspace, test_url):
        resp = await client.post(
            "/api/v1/urls/bulk/disable",
            params={"workspace_id": test_workspace.id, "url_ids": [test_url.id]},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["disabled"] >= 1

    async def test_bulk_reactivate(self, client, test_workspace, test_url):
        await client.post(
            "/api/v1/urls/bulk/disable",
            params={"workspace_id": test_workspace.id, "url_ids": [test_url.id]},
        )
        resp = await client.post(
            "/api/v1/urls/bulk/reactivate",
            params={"workspace_id": test_workspace.id, "url_ids": [test_url.id]},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["reactivated"] >= 1

    async def test_bulk_delete(self, client, test_workspace, test_url):
        resp = await client.post(
            "/api/v1/urls/bulk/delete",
            params={"workspace_id": test_workspace.id, "url_ids": [test_url.id]},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["deleted"] >= 1

    async def test_bulk_export_csv(self, client, test_workspace):
        resp = await client.get(
            "/api/v1/urls/bulk/export",
            params={"workspace_id": test_workspace.id, "format": "csv"},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.headers["content-type"] == "text/csv"
        assert "filename=urls_export.csv" in resp.headers.get("content-disposition", "")

    async def test_bulk_export_json(self, client, test_workspace):
        resp = await client.get(
            "/api/v1/urls/bulk/export",
            params={"workspace_id": test_workspace.id, "format": "json"},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.headers["content-type"] == "application/json"
        assert "filename=urls_export.json" in resp.headers.get("content-disposition", "")

    async def test_bulk_export_invalid_format(self, client, test_workspace):
        resp = await client.get(
            "/api/v1/urls/bulk/export",
            params={"workspace_id": test_workspace.id, "format": "xml"},
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_bulk_qr_zip(self, client, test_workspace, test_url):
        resp = await client.get(
            "/api/v1/urls/bulk/qr",
            params={"workspace_id": test_workspace.id, "url_ids": [test_url.id]},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.headers["content-type"] == "application/zip"
        assert "filename=qr_codes.zip" in resp.headers.get("content-disposition", "")

    async def test_bulk_no_auth(self, app, test_workspace):
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(
                "/api/v1/urls/bulk/export",
                params={"workspace_id": test_workspace.id},
            )
            assert resp.status_code == status.HTTP_401_UNAUTHORIZED
