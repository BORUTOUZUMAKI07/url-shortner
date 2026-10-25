"""Security response headers for every backend response.

The frontend sets its own headers in `next.config.ts`; this covers the API and
the redirect path, including responses produced by middleware/error handlers.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.shared.core.config import settings

_BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}

_API_CSP = "default-src 'none'; frame-ancestors 'none'"
_HSTS = "max-age=31536000; includeSubDomains"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        for name, value in _BASE_HEADERS.items():
            response.headers.setdefault(name, value)

        # HSTS only where the browser is actually on HTTPS. Render terminates
        # TLS in front of the app, so request.url.scheme is http here; the
        # environment is the reliable signal.
        if settings.ENVIRONMENT == "production":
            response.headers.setdefault("Strict-Transport-Security", _HSTS)

        # APIs return JSON; a CSP here is defence-in-depth against a browser
        # treating an error response as a document. Skip the docs/OpenAPI
        # routes, which need scripts and styles.
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Content-Security-Policy", _API_CSP)

        # Auth responses carry tokens (body on login/refresh; Set-Cookie on all
        # of them). A shared/on-disk cache must never store them.
        if request.url.path.startswith("/api/v1/auth/"):
            response.headers.setdefault("Cache-Control", "no-store")

        return response
