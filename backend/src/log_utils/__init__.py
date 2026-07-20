"""
Structured logging setup with JSON format and correlation ID support.
Exports logs via OTLP to New Relic.
"""

import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from pythonjsonlogger import jsonlogger

from src.core.config import settings


class CorrelationIdFilter(logging.Filter):
    def __init__(self, correlation_id: Optional[str] = None):
        super().__init__()
        self.correlation_id = correlation_id

    def filter(self, record):
        if not hasattr(record, 'correlation_id'):
            record.correlation_id = self.correlation_id or "no-correlation-id"
        return True


class JSONFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()
        log_record['service'] = settings.PROJECT_NAME
        log_record['environment'] = settings.ENVIRONMENT
        log_record['version'] = "1.0.0"
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
    correlation_filter: logging.Filter = CorrelationIdFilter(correlation_id)

    # Drop DEBUG in production
    if is_prod:
        class ProdFilter(logging.Filter):
            def filter(self, record):
                return record.levelno >= logging.INFO
        correlation_filter = ProdFilter()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(correlation_filter)
    logger.addHandler(console_handler)

    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{logger.name.replace('url-shortener.', '')}.log"
    file_handler = logging.FileHandler(filename=log_file, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(correlation_filter)
    logger.addHandler(file_handler)

    if settings.OTLP_ENABLED and settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "http/dup")
        try:
            from opentelemetry.sdk._logs import LoggingHandler as OTLPLoggingHandler
            from opentelemetry.sdk._logs import LoggerProvider as OTLPLoggerProvider
            from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

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
            logger.addHandler(otlp_handler)
        except Exception as e:
            logger.warning("OTLP log handler not available: %s", e)

    logger.addFilter(correlation_filter)
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


__all__ = ["setup_logging", "get_logger", "log_request_start", "log_request_end"]
