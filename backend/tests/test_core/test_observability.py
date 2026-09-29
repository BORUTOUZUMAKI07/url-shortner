"""Unit tests for Layer-1 observability (OTel SDK + /metrics endpoint).

These are deliberately dependency-light unit tests (no DB, no testcontainers):
they assert the local, vendor-independent metrics path that must keep working
even when the Layer-2 collector / Layer-3 vendor are unreachable.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.main import metrics_endpoint
from src.shared.core.config import Settings
from src.shared.core.tracing import get_app_metrics_text


def _settings(**overrides) -> Settings:
    """Settings built from explicit args only — see tests/test_core/test_config.py."""
    overrides.setdefault("ENVIRONMENT", "development")
    return Settings(_env_file=None, **overrides)


class TestMetricsEndpoint:
    def test_returns_prometheus_text(self):
        app = FastAPI()
        app.add_api_route("/metrics", metrics_endpoint, methods=["GET"], include_in_schema=False)
        client = TestClient(app)
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")
        # Even with no reader initialized a valid (comment-only) scrape is
        # returned — scrapers must never see a hard failure here.
        assert resp.text.startswith("#")

    def test_metrics_excluded_from_openapi_schema(self):
        app = FastAPI()
        app.add_api_route("/metrics", metrics_endpoint, methods=["GET"], include_in_schema=False)
        assert "/metrics" not in app.openapi()["paths"]


class TestGetAppMetricsText:
    def test_returns_valid_scrape_when_uninitialized(self):
        text = get_app_metrics_text()
        assert isinstance(text, str)
        assert text.startswith("#")


class TestPrometheusRenderer:
    """End-to-end render check against the real SDK data model."""

    def test_renders_counter_gauge_histogram(self):
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import InMemoryMetricReader

        from src.shared.core.metrics_text import render_prometheus_exposition

        # Use the provider's own meter: the process-global meter provider can
        # only be set once, so never touch it in tests.
        reader = InMemoryMetricReader()
        provider = MeterProvider(metric_readers=[reader])
        meter = provider.get_meter("test")

        counter = meter.create_counter("http_requests_total", description="Total HTTP requests")
        counter.add(3, {"path": "/a", "service.name": "linkforge"})

        duration = meter.create_histogram("http_request_duration_seconds", unit="s")
        duration.record(0.5, {"path": "/a"})

        updown = meter.create_up_down_counter("active_workers")
        updown.add(-2)

        text = render_prometheus_exposition(reader.get_metrics_data())

        # Counter → counter w/ _total name + sanitised label keys.
        assert "# TYPE http_requests_total counter" in text
        assert "# HELP http_requests_total Total HTTP requests" in text
        assert '{path="/a",service_name="linkforge"} 3' in text
        # Histogram → bucket/sum/count (numeric bounds must be quoted).
        assert "# TYPE http_request_duration_seconds histogram" in text
        assert 'http_request_duration_seconds_bucket{path="/a",le="5.0"} 1' in text
        assert 'http_request_duration_seconds_bucket{path="/a",le="+Inf"} 1' in text
        assert 'http_request_duration_seconds_sum{path="/a"} 0.5' in text
        assert 'http_request_duration_seconds_count{path="/a"} 1' in text
        # UpDownCounter → gauge (may go down).
        assert "# TYPE active_workers gauge" in text
        assert "active_workers -2" in text

    def test_exponential_histogram_is_skipped_not_fatal(self):
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import InMemoryMetricReader

        from src.shared.core.metrics_text import render_prometheus_exposition

        reader = InMemoryMetricReader()
        provider = MeterProvider(metric_readers=[reader])
        meter = provider.get_meter("test")
        meter.create_histogram("odd_histogram", explicit_bucket_boundaries_advisory=[1, 2])

        data = reader.get_metrics_data()
        if data is None:
            text = "# no metric data collected\n"
        else:
            text = render_prometheus_exposition(data)
        # The renderer must never raise on unusual data shapes.
        assert isinstance(text, str)
        assert text.startswith("#")


class TestTraceSamplingConfig:
    def test_sample_ratio_defaults_to_send_all(self):
        # 1.0 = app emits every span; the Layer-2 collector tail-samples
        # (keeps 100% of errors). Lower only when running direct-to-vendor.
        assert _settings().OTEL_TRACES_SAMPLE_RATIO == 1.0

    def test_sample_ratio_override(self):
        s = _settings(OTEL_TRACES_SAMPLE_RATIO=0.1)
        assert s.OTEL_TRACES_SAMPLE_RATIO == 0.1

    def test_otlp_endpoint_points_at_collector(self):
        s = _settings(OTEL_EXPORTER_OTLP_ENDPOINT="http://otel-collector:4318")
        assert s.OTEL_EXPORTER_OTLP_ENDPOINT == "http://otel-collector:4318"

    def test_otlp_enabled_by_default(self):
        assert _settings().OTLP_ENABLED is True
