"""Single source of truth for resolving the real client IP.

Historically ``request.client.host`` was used directly in the rate-limit
middleware, the audit-context middleware and the redirect route. Behind a
reverse proxy (Render, any ingress) ``request.client.host`` is the *proxy's*
address, not the end user's — uvicorn is intentionally NOT started with
``--proxy-headers`` here. That made every consumer share one rate-limit bucket
(one abusive client throttled the whole platform) and stamped the proxy IP on
every audit row.

Resolution rules (unchanged semantics, now centralised):

* ``X-Forwarded-For`` is only consulted when ``settings.TRUST_PROXY`` is on.
* The **rightmost** entry is the one appended by the trusted proxy, so it is the
  real client. The leftmost entry is client-controlled and must never be used —
  otherwise anyone could spoof their IP and poison rate-limiting or geo lookups.
* Falls back to the socket peer (correct when there is no proxy at all).
"""

from fastapi import Request

from src.shared.core.config import settings


def get_client_ip(request: Request) -> str:
    """Return the best-known client IP for *request*."""
    if settings.TRUST_PROXY:
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            parts = [p.strip() for p in xff.split(",") if p.strip()]
            if parts:
                return parts[-1]
    return request.client.host if request.client else "unknown"
