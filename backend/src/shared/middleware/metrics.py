"""
Metrics middleware for FastAPI.
Records HTTP request metrics (latency, error rates, etc.).
"""

import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.core.metrics import record_http_request


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware that records HTTP request metrics.
    """

    # Paths to exclude from metrics
    EXCLUDED_PATHS = {"/health", "/metrics", "/docs", "/openapi.json", "/redoc"}

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
                endpoint=request.url.path,
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
                endpoint=request.url.path,
                status_code=500,  # Internal server error
                duration_seconds=duration_seconds,
                error=True
            )

            raise
