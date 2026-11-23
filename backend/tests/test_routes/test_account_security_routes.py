import time

import pyotp
from fastapi import status


def _totp_code_for_next_window(secret: str) -> str:
    """Return a TOTP code for the next 30s window.

    Tests confirm 2FA with the current-window code, which advances replay
    protection to that counter. A second code in the same window would be
    correctly rejected as a replay, so follow-up actions in tests use the next
    window's code.
    """
    totp = pyotp.TOTP(secret)
    return totp.generate_otp(int(time.time()) // 30 + 1)


class TestSessionRoutes:
    async def test_list_sessions_requires_auth(self, unauth_client):
        resp = await unauth_client.get("/api/v1/auth/sessions")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_list_sessions_empty_initially(self, client):
        resp = await client.get("/api/v1/auth/sessions")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    async def test_login_creates_session_and_list_shows_it(self, app, db, test_user):
        from httpx import ASGITransport, AsyncClient

        from src.shared.core.deps import get_db

        app.dependency_overrides[get_db] = lambda: db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            login = await ac.post("/api/v1/auth/login", json={
                "email": test_user.email,
                "password": "testpass123",
            })
            assert login.status_code == status.HTTP_200_OK
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            resp = await ac.get("/api/v1/auth/sessions", headers=headers)
            assert resp.status_code == status.HTTP_200_OK
            sessions = resp.json()["sessions"]
            assert len(sessions) >= 1
            assert any(s["is_current"] for s in sessions)
            for s in sessions:
                assert "id" in s
                assert "user_agent" in s or s.get("user_agent") is None

    async def test_revoke_other_sessions(self, app, db, test_user):
        from httpx import ASGITransport, AsyncClient

        from src.shared.core.deps import get_db

        app.dependency_overrides[get_db] = lambda: db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Create two sessions
            login1 = await ac.post("/api/v1/auth/login", json={"email": test_user.email, "password": "testpass123"})
            login2 = await ac.post("/api/v1/auth/login", json={"email": test_user.email, "password": "testpass123"})
            assert login1.status_code == 200
            assert login2.status_code == 200

            token2 = login2.json()["access_token"]
            headers2 = {"Authorization": f"Bearer {token2}"}

            listed = await ac.get("/api/v1/auth/sessions", headers=headers2)
            assert listed.status_code == 200
            sessions = listed.json()["sessions"]
            assert len(sessions) >= 2

            revoke = await ac.delete("/api/v1/auth/sessions", headers=headers2)
            assert revoke.status_code == 200
            assert "Revoked" in revoke.json()["detail"]

            listed2 = await ac.get("/api/v1/auth/sessions", headers=headers2)
            assert listed2.status_code == 200
            sessions2 = listed2.json()["sessions"]
            # Only current should remain
            assert len(sessions2) == 1
            assert sessions2[0]["is_current"] is True

    async def test_revoke_specific_session(self, app, db, test_user):
        from httpx import ASGITransport, AsyncClient

        from src.shared.core.deps import get_db

        app.dependency_overrides[get_db] = lambda: db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post("/api/v1/auth/login", json={"email": test_user.email, "password": "testpass123"})
            login2 = await ac.post("/api/v1/auth/login", json={"email": test_user.email, "password": "testpass123"})
            token2 = login2.json()["access_token"]
            headers2 = {"Authorization": f"Bearer {token2}"}

            sessions = (await ac.get("/api/v1/auth/sessions", headers=headers2)).json()["sessions"]
            other = next(s for s in sessions if not s["is_current"])

            resp = await ac.delete(f"/api/v1/auth/sessions/{other['id']}", headers=headers2)
            assert resp.status_code == 200

            sessions_after = (await ac.get("/api/v1/auth/sessions", headers=headers2)).json()["sessions"]
            ids = {s["id"] for s in sessions_after}
            assert other["id"] not in ids


class TestTwoFactorRoutes:
    async def test_2fa_status_default_disabled(self, client):
        resp = await client.get("/api/v1/profile/2fa")
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["recovery_codes_remaining"] == 0

    async def test_2fa_setup_confirm_and_login_challenge(self, app, db, test_user):
        from httpx import ASGITransport, AsyncClient

        from src.shared.core.deps import get_db

        app.dependency_overrides[get_db] = lambda: db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            login = await ac.post("/api/v1/auth/login", json={"email": test_user.email, "password": "testpass123"})
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Begin setup
            setup = await ac.post("/api/v1/profile/2fa/setup", json={"current_password": "testpass123"}, headers=headers)
            assert setup.status_code == 200
            setup_data = setup.json()
            assert "secret" in setup_data
            assert "otpauth_uri" in setup_data
            assert setup_data["qr_code_data_uri"].startswith("data:image/png;base64,")

            # Confirm setup
            totp = pyotp.TOTP(setup_data["secret"])
            code = totp.now()
            confirm = await ac.post("/api/v1/profile/2fa/confirm", json={"code": code}, headers=headers)
            assert confirm.status_code == 200
            recovery = confirm.json()["recovery_codes"]
            assert len(recovery) == 8
            assert all("-" in c for c in recovery)

            # Status should be enabled
            status_resp = await ac.get("/api/v1/profile/2fa", headers=headers)
            assert status_resp.status_code == 200
            assert status_resp.json()["enabled"] is True
            assert status_resp.json()["recovery_codes_remaining"] == 8

            # New login should require 2FA
            login2 = await ac.post("/api/v1/auth/login", json={"email": test_user.email, "password": "testpass123"})
            assert login2.status_code == 200
            body = login2.json()
            assert body["two_factor_required"] is True
            assert body["challenge_token"]
            assert body.get("access_token") is None

            # Wrong code should fail and consume the single-use challenge
            bad = await ac.post("/api/v1/auth/2fa/verify", json={"challenge_token": body["challenge_token"], "code": "000000"})
            assert bad.status_code == 401

            # Replayed/consumed challenge must be rejected
            replay = await ac.post("/api/v1/auth/2fa/verify", json={"challenge_token": body["challenge_token"], "code": _totp_code_for_next_window(setup_data["secret"])})
            assert replay.status_code in (401, 403)

            # Fresh challenge with correct TOTP should succeed
            login3 = await ac.post("/api/v1/auth/login", json={"email": test_user.email, "password": "testpass123"})
            assert login3.status_code == 200
            body3 = login3.json()
            assert body3["two_factor_required"] is True
            code2 = _totp_code_for_next_window(setup_data["secret"])
            ok = await ac.post("/api/v1/auth/2fa/verify", json={"challenge_token": body3["challenge_token"], "code": code2})
            assert ok.status_code == 200
            ok_body = ok.json()
            assert ok_body["access_token"]
            assert ok_body["token_type"] == "bearer"

    async def test_2fa_recovery_code_login(self, app, db, test_user):
        from httpx import ASGITransport, AsyncClient

        from src.shared.core.deps import get_db

        app.dependency_overrides[get_db] = lambda: db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            login = await ac.post("/api/v1/auth/login", json={"email": test_user.email, "password": "testpass123"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            setup = await ac.post("/api/v1/profile/2fa/setup", json={"current_password": "testpass123"}, headers=headers)
            secret = setup.json()["secret"]
            confirm = await ac.post("/api/v1/profile/2fa/confirm", json={"code": pyotp.TOTP(secret).now()}, headers=headers)
            recovery_codes = confirm.json()["recovery_codes"]

            login2 = await ac.post("/api/v1/auth/login", json={"email": test_user.email, "password": "testpass123"})
            challenge = login2.json()["challenge_token"]

            ok = await ac.post("/api/v1/auth/2fa/verify", json={"challenge_token": challenge, "code": recovery_codes[0]})
            assert ok.status_code == 200
            assert ok.json()["access_token"]

            # Same recovery code should not work again on a new challenge
            login3 = await ac.post("/api/v1/auth/login", json={"email": test_user.email, "password": "testpass123"})
            challenge3 = login3.json()["challenge_token"]
            reuse = await ac.post("/api/v1/auth/2fa/verify", json={"challenge_token": challenge3, "code": recovery_codes[0]})
            assert reuse.status_code == 401

    async def test_2fa_disable(self, app, db, test_user):
        from httpx import ASGITransport, AsyncClient

        from src.shared.core.deps import get_db

        app.dependency_overrides[get_db] = lambda: db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            login = await ac.post("/api/v1/auth/login", json={"email": test_user.email, "password": "testpass123"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            setup = await ac.post("/api/v1/profile/2fa/setup", json={"current_password": "testpass123"}, headers=headers)
            secret = setup.json()["secret"]
            await ac.post("/api/v1/profile/2fa/confirm", json={"code": pyotp.TOTP(secret).now()}, headers=headers)

            disable = await ac.post("/api/v1/profile/2fa/disable", json={
                "current_password": "testpass123",
                "code": _totp_code_for_next_window(secret),
            }, headers=headers)
            assert disable.status_code == 200

            status_resp = await ac.get("/api/v1/profile/2fa", headers=headers)
            assert status_resp.json()["enabled"] is False

            # Login should no longer require 2FA
            login2 = await ac.post("/api/v1/auth/login", json={"email": test_user.email, "password": "testpass123"})
            assert login2.status_code == 200
            assert login2.json().get("two_factor_required") is False
            assert login2.json().get("access_token")


class TestAccountExportDelete:
    async def test_export_account(self, client):
        resp = await client.get("/api/v1/profile/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "profile" in data
        assert "workspaces" in data
        assert "links" in data
        assert "api_keys" in data
        assert "favorites" in data
        assert "audit_retention_policy" in data
        assert data["profile"]["email"] == "test@example.com"

    async def test_delete_account_requires_confirmation(self, client):
        resp = await client.request("DELETE", "/api/v1/profile/account", json={
            "current_password": "testpass123",
            "confirmation": "NOPE",
        })
        assert resp.status_code == 400

    async def test_delete_account_wrong_password(self, client):
        resp = await client.request("DELETE", "/api/v1/profile/account", json={
            "current_password": "wrong",
            "confirmation": "DELETE",
        })
        assert resp.status_code == 400

    async def test_delete_account_success(self, app, db, test_user):
        from httpx import ASGITransport, AsyncClient

        from src.shared.core.deps import get_db

        app.dependency_overrides[get_db] = lambda: db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            login = await ac.post("/api/v1/auth/login", json={"email": test_user.email, "password": "testpass123"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            resp = await ac.request("DELETE", "/api/v1/profile/account", json={
                "current_password": "testpass123",
                "confirmation": "DELETE",
            }, headers=headers)
            assert resp.status_code == 200
            assert "deleted" in resp.json()["detail"].lower()

            # User should be gone
            me = await ac.get("/api/v1/auth/me", headers=headers)
            assert me.status_code in (401, 404)
