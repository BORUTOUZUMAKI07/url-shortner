"""Regression tests for the password-unlock same-origin guard.

A password-protected short link is served by whichever origin the visitor opened
it on, and its ``<form>`` has no ``action``, so it posts back to that *same*
origin. The frontend proxies ``/{short_code}`` to the backend (``next.config.ts``)
and the app copies short links at ``window.location.origin`` — i.e. the frontend
domain — so the normal Referer on that POST is the frontend origin.

The guard used to accept only ``BACKEND_URL``, so unlocking a protected link from
the URL the app itself hands out always answered 404. ``_check_same_origin`` is a
pure function of the request headers plus two settings, so these tests need no
database and no server.
"""

import pytest
from starlette.datastructures import Headers
from starlette.requests import Request

from src.links.routes.redirect import _check_same_origin
from src.shared.errors import URLNotFound

BACKEND_ORIGIN = "https://api.linkforge.test"
FRONTEND_ORIGIN = "https://app.linkforge.test"


@pytest.fixture(autouse=True)
def _fixed_origins(monkeypatch):
    # Pin distinct origins so the two branches cannot be confused, regardless of
    # whatever .env the suite happens to run against.
    monkeypatch.setattr(
        "src.links.routes.redirect.settings.BACKEND_URL", BACKEND_ORIGIN
    )
    monkeypatch.setattr(
        "src.links.routes.redirect.settings.FRONTEND_URL", FRONTEND_ORIGIN
    )


def _post_with_referer(referer: str | None) -> Request:
    headers = Headers({"referer": referer} if referer is not None else {})
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/abc",
        "headers": headers.raw,
    }
    return Request(scope)


class TestSameOriginGuard:
    def test_missing_referer_is_allowed(self):
        # No referer to compare: rejecting it would break the form for browsers
        # that omit the header, and there is nothing to spoof.
        _check_same_origin(_post_with_referer(None))

    def test_backend_origin_is_allowed(self):
        _check_same_origin(_post_with_referer(f"{BACKEND_ORIGIN}/abc"))

    def test_frontend_origin_is_allowed(self):
        # The regression: this is the Referer produced by unlocking a link opened
        # through the copied frontend URL.
        _check_same_origin(_post_with_referer(f"{FRONTEND_ORIGIN}/abc"))

    def test_match_ignores_scheme_port_and_path(self):
        _check_same_origin(
            _post_with_referer("https://app.linkforge.test:8443/deep/path?x=1")
        )

    def test_foreign_origin_is_rejected(self):
        with pytest.raises(URLNotFound):
            _check_same_origin(_post_with_referer("https://attacker.invalid/abc"))

    def test_lookalike_host_is_not_a_match(self):
        # A host that merely *contains* an allowed one must not pass: the check
        # compares the parsed hostname exactly, never a substring.
        with pytest.raises(URLNotFound):
            _check_same_origin(
                _post_with_referer("https://app.linkforge.test.evil.invalid/abc")
            )

    def test_rejected_origin_is_a_not_found_not_forbidden(self):
        # 404 rather than 403 so the guard does not become an existence oracle
        # for short codes on other tenants.
        with pytest.raises(URLNotFound) as exc:
            _check_same_origin(_post_with_referer("https://attacker.invalid/"))
        assert exc.value.status_code == 404
