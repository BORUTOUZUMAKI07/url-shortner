"""
Structured logging setup with JSON format and correlation ID support.
Exports logs via OTLP to New Relic.
"""

import logging
import os
import sys
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from opentelemetry import trace
from pythonjsonlogger import jsonlogger

from src.shared.core.config import settings
from src.shared.core.redaction import RedactionFilter

# Correlation ids live in a ContextVar, not on the logger. `setup_logging()` is
# called exactly once per process (main.py / each run_worker_*.py), so a value
# captured at setup time can never describe a *request*. A ContextVar is
# request-scoped: the tracing middleware sets it before `call_next`, and every
# log record emitted downstream (including from spawned tasks, which inherit a
# copy of the context) picks it up.
_correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def set_correlation_id(correlation_id: str) -> Token:
    """Bind a correlation id to the current (request) context."""
    return _correlation_id_var.set(correlation_id)


def reset_correlation_id(token: Token) -> None:
    """Restore the previous context value (call in a ``finally``)."""
    _correlation_id_var.reset(token)


def get_correlation_id() -> Optional[str]:
    """Return the correlation id bound to the current context, if any."""
    return _correlation_id_var.get()


class CorrelationIdFilter(logging.Filter):
    def __init__(self, correlation_id: Optional[str] = None):
        super().__init__()
        self.correlation_id = correlation_id

    def filter(self, record):
        if not getattr(record, "correlation_id", None):
            record.correlation_id = (
                get_correlation_id() or self.correlation_id or "no-correlation-id"
            )
        return True


class JSONFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        # UTC everywhere: the old fixed +05:30 offset made every log line
        # disagree with the UTC timestamps in traces, metrics and New Relic.
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat()
        log_record['service'] = settings.PROJECT_NAME
        log_record['environment'] = settings.ENVIRONMENT
        log_record['version'] = "1.0.0"
        # Join logs to traces: when a span is active, stamp its ids so a log
        # line can be found from the trace (and vice versa) in New Relic.
        span_context = trace.get_current_span().get_span_context()
        if span_context is not None and span_context.is_valid:
            log_record.setdefault('trace_id', format(span_context.trace_id, '032x'))
            log_record.setdefault('span_id', format(span_context.span_id, '016x'))
        if hasattr(record, 'correlation_id'):
            log_record['correlation_id'] = record.correlation_id
        for attr in ('trace_id', 'span_id', 'user_id', 'workspace_id', 'url_id'):
            if hasattr(record, attr):
                log_record[attr] = getattr(record, attr)


def setup_logging(correlation_id: Optional[str] = None):
    logger = logging.getLogger("url-shortener")
    is_prod = settings.ENVIRONMENT == "production"
    log_level = logging.INFO if is_prod else logging.DEBUG
    logger.setLevel(log_level)
    logger.handlers.clear()
    formatter = JSONFormatter(fmt='%(timestamp)s %(level)s %(name)s %(message)s', timestamp=True)

    # Handler-level filters, applied in order. They live on the *handlers*
    # because a logger's own filters are not consulted for records logged on
    # its children (url-shortener.redirect_service, …) — which is why the old
    # logger-level CorrelationIdFilter only ever saw records logged on the base
    # logger.
    handler_filters: list[logging.Filter] = []
    if is_prod:
        # Drop DEBUG in production.
        class ProdFilter(logging.Filter):
            def filter(self, record):
                return record.levelno >= logging.INFO
        handler_filters.append(ProdFilter())
    handler_filters.append(CorrelationIdFilter(correlation_id))
    if settings.PII_REDACTION_ENABLED:
        handler_filters.append(RedactionFilter())

    def _attach(handler: logging.Handler) -> None:
        for handler_filter in handler_filters:
            handler.addFilter(handler_filter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    _attach(console_handler)
    logger.addHandler(console_handler)

    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{logger.name.replace('url-shortener.', '')}.log"
        file_handler = logging.FileHandler(filename=log_file, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        _attach(file_handler)
        logger.addHandler(file_handler)
    except OSError as e:
        # e.g. read-only filesystem in a container running as non-root.
        # Console logging is unaffected.
        logger.warning("File logging disabled: %s", e)

    if settings.OTLP_ENABLED and settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "http/dup")
        try:
            from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
            from opentelemetry.sdk._logs import LoggerProvider as OTLPLoggerProvider
            from opentelemetry.sdk._logs import LoggingHandler as OTLPLoggingHandler
            from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
            from opentelemetry.sdk.resources import Resource

            headers = {}
            if settings.OTEL_EXPORTER_OTLP_HEADERS:
                for pair in settings.OTEL_EXPORTER_OTLP_HEADERS.split(","):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        headers[k.strip()] = v.strip()

            otlp_log_exporter = OTLPLogExporter(
                endpoint=f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/logs",
                headers=headers,
                timeout=10,
            )
            log_resource = Resource.create({
                "service.name": settings.PROJECT_NAME or "url-shortener",
                "service.version": "1.0.0",
                "environment": settings.ENVIRONMENT,
            })
            log_provider = OTLPLoggerProvider(resource=log_resource)
            log_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_log_exporter))
            otlp_handler = OTLPLoggingHandler(logger_provider=log_provider, level=logging.INFO)
            _attach(otlp_handler)
            logger.addHandler(otlp_handler)
        except Exception as e:
            logger.warning("OTLP log handler not available: %s", e)

    # Belt-and-braces: also tag records logged directly on the base logger, so
    # `logger.info(...)` on the package logger carries the id before handlers.
    logger.addFilter(CorrelationIdFilter(correlation_id))
    return logger


def get_logger(name: str = "url-shortener") -> logging.Logger:
    if name != "url-shortener" and not name.startswith("url-shortener."):
        name = f"url-shortener.{name}"
    return logging.getLogger(name)


def log_request_start(logger: logging.Logger, method: str, path: str, correlation_id: str):
    logger.info(
        f"Request started: {method} {path}",
        extra={"correlation_id": correlation_id, "event": "request_start", "http_method": method, "http_path": path}
    )


def log_request_end(logger: logging.Logger, method: str, path: str, status_code: int, duration_ms: float, correlation_id: str):
    logger.info(
        f"Request completed: {method} {path} \u2192 {status_code} ({duration_ms:.2f}ms)",
        extra={"correlation_id": correlation_id, "event": "request_end", "http_method": method, "http_path": path, "http_status_code": status_code, "duration_ms": duration_ms}
    )


__all__ = [
    "setup_logging",
    "get_logger",
    "log_request_start",
    "log_request_end",
    "get_correlation_id",
    "set_correlation_id",
    "reset_correlation_id",
]
