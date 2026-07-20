import os
import uuid

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from src.core.config import settings
from src.log_utils import get_logger

logger = get_logger(__name__)


def _inject_otlp_env():
    """Inject OTLP env vars so OTel SDK components find them via os.environ."""
    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    if settings.OTEL_EXPORTER_OTLP_HEADERS:
        os.environ.setdefault("OTEL_EXPORTER_OTLP_HEADERS", settings.OTEL_EXPORTER_OTLP_HEADERS)
    os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "http/dup")


# Ensure env vars are set before any OTLP exporters are created
_inject_otlp_env()


def _get_otlp_headers() -> dict:
    headers = {}
    if settings.OTEL_EXPORTER_OTLP_HEADERS:
        for pair in settings.OTEL_EXPORTER_OTLP_HEADERS.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                headers[k.strip()] = v.strip()
    return headers


def init_tracing():
    if not settings.OTLP_ENABLED:
        logger.info("Tracing disabled, using no-op tracer")
        trace.set_tracer_provider(TracerProvider())
        return

    resource = Resource.create({
        "service.name": settings.PROJECT_NAME,
        "service.version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "deployment.environment": settings.ENVIRONMENT,
    })

    try:
        otlp_exporter = OTLPSpanExporter(
            endpoint=f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces",
            headers=_get_otlp_headers(),
            timeout=10,
        )
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        trace.set_tracer_provider(tracer_provider)
        logger.info("OTLP tracing initialized")
    except Exception as e:
        logger.warning("Failed to initialize OTLP tracing: %s", e)
        trace.set_tracer_provider(TracerProvider(resource=resource))


def init_metrics():
    if not settings.OTLP_ENABLED:
        logger.info("Metrics disabled, using no-op meter")
        metrics.set_meter_provider(MeterProvider())
        return

    try:
        otlp_exporter = OTLPMetricExporter(
            endpoint=f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/metrics",
            headers=_get_otlp_headers(),
            timeout=10,
        )
        reader = PeriodicExportingMetricReader(otlp_exporter, export_interval_millis=60000)
        resource = Resource.create({
            "service.name": settings.PROJECT_NAME,
            "environment": settings.ENVIRONMENT,
        })
        meter_provider = MeterProvider(metric_readers=[reader], resource=resource)
        metrics.set_meter_provider(meter_provider)
        logger.info("OTLP metrics initialized")
    except Exception as e:
        logger.warning("Failed to initialize OTLP metrics: %s", e)
        metrics.set_meter_provider(MeterProvider())


def instrument_fastapi(app):
    try:
        FastAPIInstrumentor.instrument_app(app, excluded_urls="/health")
        logger.info("FastAPI instrumented")
    except Exception as e:
        logger.warning("Failed to instrument FastAPI: %s", e)


def instrument_sqlalchemy(engine):
    try:
        SQLAlchemyInstrumentor().instrument(engine=engine, service=settings.PROJECT_NAME)
        logger.info("SQLAlchemy instrumented")
    except Exception as e:
        logger.warning("Failed to instrument SQLAlchemy: %s", e)


def instrument_redis(client):
    try:
        RedisInstrumentor().instrument(client=client, service=settings.PROJECT_NAME)
        logger.info("Redis instrumented")
    except Exception as e:
        logger.warning("Failed to instrument Redis: %s", e)


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name, version="1.0.0")


def get_meter(name: str) -> metrics.Meter:
    return metrics.get_meter(name, version="1.0.0")


def generate_correlation_id() -> str:
    return f"req-{uuid.uuid4().hex[:12]}"
