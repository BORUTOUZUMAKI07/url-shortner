"""
Tracing middleware for FastAPI.
Adds correlation IDs and trace context to all requests.
"""

import time

from fastapi import Request
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared import get_logger, log_request_end, log_request_start
from src.shared.core.tracing import generate_correlation_id


class TracingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds tracing and correlation IDs to all requests.
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

        # Get logger and tracer
        logger = get_logger()
        tracer = trace.get_tracer(__name__)

        # Create span for this request
        span_attributes = {
            "http.method": request.method,
            "http.url": str(request.url),
            "http.target": request.url.path,
            "correlation_id": correlation_id,
        }

        # Log request start
        log_request_start(
            logger,
            request.method,
            request.url.path,
            correlation_id
        )

        # Time the request
        start_time = time.time()

        with tracer.start_as_current_span(
            f"{request.method} {request.url.path}",
            attributes=span_attributes
        ) as span:
            try:
                # Process request
                response = await call_next(request)

                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Add response info to span
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("http.response_time_ms", duration_ms)

                # Mark span as success
                span.set_status(Status(StatusCode.OK))

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
                # Mark span as error
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)

                # Log error
                logger.error(
                    f"Request failed: {str(e)}",
                    extra={
                        "correlation_id": correlation_id,
                        "event": "request_error",
                        "error_type": type(e).__name__,
                    }
                )

                raise
