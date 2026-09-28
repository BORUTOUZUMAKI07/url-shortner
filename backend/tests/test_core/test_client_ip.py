"""Regression tests for the client-IP resolver.

Every consumer (rate limiting, audit context, redirect geo/rate limits, webhook
receiver source IP) used to read ``request.client.host`` directly. Uvicorn is
deliberately NOT started with ``--proxy-headers`` here, so behind Render that
value is the *proxy's* address: every visitor collapsed into one rate-limit
bucket (a single abusive client throttled the whole platform) and every audit
row was stamped with the proxy IP.
"""

import pytest
from starlette.datastructures import Headers
from starlette.requests import Request

from src.shared.core.client_ip import get_client_ip


def _request(peer: str | None, xff: str | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": Headers({"x-forwarded-for": xff} if xff else {}).raw,
        "client": (peer, 1234) if peer else None,
    }
    return Request(scope)


@pytest.fixture(autouse=True)
def _trust_proxy(monkeypatch):
    """Default to the deployed configuration (behind a reverse proxy)."""
    monkeypatch.setattr("src.shared.core.client_ip.settings.TRUST_PROXY", True)


class TestWithTrustedProxy:
    def test_uses_rightmost_forwarded_entry(self):
        # Leftmost is client-controlled and must never win, or anyone could
        # spoof their IP and escape (or poison) rate limiting.
        req = _request("10.0.0.1", "1.1.1.1, 2.2.2.2, 3.3.3.3")
        assert get_client_ip(req) == "3.3.3.3"

    def test_single_forwarded_entry(self):
        assert get_client_ip(_request("10.0.0.1", "9.9.9.9")) == "9.9.9.9"

    def test_whitespace_is_tolerated(self):
        req = _request("10.0.0.1", "1.1.1.1 ,  2.2.2.2 ")
        assert get_client_ip(req) == "2.2.2.2"

    def test_falls_back_to_peer_without_header(self):
        assert get_client_ip(_request("10.0.0.1")) == "10.0.0.1"

    def test_ignores_empty_forwarded_value(self):
        assert get_client_ip(_request("10.0.0.1", "  ,  ")) == "10.0.0.1"


class TestWithoutTrustedProxy:
    @pytest.fixture(autouse=True)
    def _no_trust(self, monkeypatch):
        monkeypatch.setattr("src.shared.core.client_ip.settings.TRUST_PROXY", False)

    def test_header_is_ignored(self):
        # Untrusted header: honouring it would let any client impersonate
        # another and dodge per-IP limits entirely.
        req = _request("10.0.0.1", "1.1.1.1")
        assert get_client_ip(req) == "10.0.0.1"

    def test_missing_peer(self):
        assert get_client_ip(_request(None)) == "unknown"
