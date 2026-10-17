"""
Tracing middleware for FastAPI.
Adds correlation IDs and trace context to all requests.
"""

import time

from fastapi import Request
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared import (
    get_logger,
    log_request_end,
    log_request_start,
    reset_correlation_id,
    set_correlation_id,
)
from src.shared.core.tracing import generate_correlation_id


class TracingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds tracing and correlation IDs to all requests.

    It does **not** start a span. ``FastAPIInstrumentor`` is added after this
    middleware and therefore wraps it from the outside, producing the real
    server span; starting one here as well emitted a second, nested server span
    for every request (double trace volume, confusing waterfalls). Instead this
    middleware enriches the instrumented span and owns the correlation id.
    """

    async def dispatch(self, request: Request, call_next):
        # Generate or extract correlation ID
        correlation_id = request.headers.get(
            "X-Correlation-ID",
            generate_correlation_id()
        )

        # Extract trace context from headers (if using W3C Trace Context)
        # This allows correlation with distributed traces
        trace_id = request.headers.get("traceparent", "")

        # Store in request state
        request.state.correlation_id = correlation_id
        request.state.trace_id = trace_id

        # Bind to the context so *every* log record emitted while handling this
        # request carries the id — including records from child loggers and
        # tasks spawned downstream (they inherit a copy of this context).
        context_token = set_correlation_id(correlation_id)

        # Get logger and the span owned by FastAPIInstrumentor (no-op when
        # instrument_fastapi is disabled or the URL is excluded).
        logger = get_logger()
        span = trace.get_current_span()

        # Log request start
        log_request_start(
            logger,
            request.method,
            request.url.path,
            correlation_id
        )

        # Time the request
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Add response info to the instrumented span. Status is left to the
            # instrumentor: it maps the HTTP status (including 5xx → ERROR)
            # after this middleware returns.
            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("http.response_time_ms", duration_ms)
            span.set_attribute("correlation_id", correlation_id)

            # Log request end
            log_request_end(
                logger,
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                correlation_id
            )

            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id

            return response

        except Exception as e:
            # FastAPIInstrumentor records the exception and sets ERROR on this
            # same span; recording it here too would duplicate the event.
            logger.error(
                f"Request failed: {str(e)}",
                extra={
                    "correlation_id": correlation_id,
                    "event": "request_error",
                    "error_type": type(e).__name__,
                }
            )

            raise
        finally:
            reset_correlation_id(context_token)
