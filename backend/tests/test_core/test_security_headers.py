from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.middleware.security_headers import SecurityHeadersMiddleware


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/api/thing")
    async def api_thing():
        return {"ok": True}

    @app.get("/docs-like")
    async def docs_like():
        return {"ok": True}

    @app.post("/api/v1/auth/login")
    async def auth_login():
        return {"ok": True}

    return TestClient(app)


def test_common_headers_on_api_responses(monkeypatch):
    monkeypatch.setattr("src.shared.middleware.security_headers.settings.ENVIRONMENT", "test")
    r = _client().get("/api/thing")
    assert r.status_code == 200
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert r.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert r.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert r.headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert "Strict-Transport-Security" not in r.headers


def test_hsts_only_in_production(monkeypatch):
    monkeypatch.setattr("src.shared.middleware.security_headers.settings.ENVIRONMENT", "production")
    r = _client().get("/api/thing")
    assert r.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"


def test_api_csp_does_not_apply_to_docs(monkeypatch):
    monkeypatch.setattr("src.shared.middleware.security_headers.settings.ENVIRONMENT", "test")
    r = _client().get("/docs-like")
    assert "Content-Security-Policy" not in r.headers
    assert r.headers["X-Frame-Options"] == "DENY"


def test_auth_responses_are_not_cacheable(monkeypatch):
    monkeypatch.setattr("src.shared.middleware.security_headers.settings.ENVIRONMENT", "test")
    r = _client().post("/api/v1/auth/login")
    assert r.headers["Cache-Control"] == "no-store"
