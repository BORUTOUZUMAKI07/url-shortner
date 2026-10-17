"""
Metrics middleware for FastAPI.
Records HTTP request metrics (latency, error rates, etc.).
"""

import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.core.metrics import record_http_request


def endpoint_label(request: Request) -> str:
    """Return a bounded label for the request's route.

    ``request.url.path`` is *raw* — ``/api/v1/urls/1234`` and
    ``/api/v1/urls/5678`` become two distinct time series, and every short code
    hit on the redirect catch-all creates another. With a handful of links the
    metric becomes unusable and the exporter payload huge.

    FastAPI's ``APIRoute.matches`` stores the route on ``scope["route"]``, whose
    ``.path`` is the *template* (``/api/v1/urls/{url_id}``, ``/{short_code}``).
    Routing happens inside ``call_next``, so by the time we read the scope the
    route is set; if it is not (e.g. the request never matched a route), fall
    back to the raw path rather than emitting an empty label.
    """
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return request.url.path


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware that records HTTP request metrics.
    """

    # Paths to exclude from metrics. `/api/v1/ping` is the keep-warm probe
    # (hit every minute by cron-job.org); counting it would drown real traffic
    # and make the request-rate alert meaningless.
    EXCLUDED_PATHS = {"/health", "/metrics", "/docs", "/openapi.json", "/redoc", "/api/v1/ping"}

    async def dispatch(self, request: Request, call_next):
        # Skip metrics for excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Time the request
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration in seconds
            duration_seconds = time.time() - start_time

            # Determine if error
            is_error = response.status_code >= 400

            # Record metrics
            record_http_request(
                method=request.method,
                endpoint=endpoint_label(request),
                status_code=response.status_code,
                duration_seconds=duration_seconds,
                error=is_error
            )

            return response

        except Exception:
            # Calculate duration
            duration_seconds = time.time() - start_time

            # Record error metric
            record_http_request(
                method=request.method,
                endpoint=endpoint_label(request),
                status_code=500,  # Internal server error
                duration_seconds=duration_seconds,
                error=True
            )

            raise
