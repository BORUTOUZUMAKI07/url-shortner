"""
Prometheus metrics collection and tracking.
Defines all metrics used throughout the application.
"""


from opentelemetry import metrics
from opentelemetry.metrics import Counter, Histogram, UpDownCounter


class URLShortenerMetrics:
    """Collection of all application metrics."""

    # Counters (monotonically increasing)
    http_requests_total: Counter
    http_request_errors_total: Counter
    url_creation_total: Counter
    url_redirects_total: Counter
    cache_hits_total: Counter
    cache_misses_total: Counter
    api_key_requests_total: Counter
    analytics_events_processed_total: Counter
    kafka_messages_produced_total: Counter
    kafka_messages_consumed_total: Counter

    # Histograms (distribution tracking)
    http_request_duration_seconds: Histogram
    database_query_duration_seconds: Histogram
    cache_lookup_duration_seconds: Histogram
    kafka_latency_seconds: Histogram

    # Gauges (current value)
    active_workers: UpDownCounter

    def __init__(self):
        """Initialize all metrics."""
        meter = metrics.get_meter("url-shortener")

        # --- Counters ---
        self.http_requests_total = meter.create_counter(
            name="http_requests_total",
            description="Total HTTP requests",
            unit="1",
        )

        self.http_request_errors_total = meter.create_counter(
            name="http_request_errors_total",
            description="Total HTTP request errors",
            unit="1",
        )

        self.url_creation_total = meter.create_counter(
            name="url_creation_total",
            description="Total URLs created",
            unit="1",
        )

        self.url_redirects_total = meter.create_counter(
            name="url_redirects_total",
            description="Total URL redirects (clicks)",
            unit="1",
        )

        self.cache_hits_total = meter.create_counter(
            name="cache_hits_total",
            description="Total Redis cache hits",
            unit="1",
        )

        self.cache_misses_total = meter.create_counter(
            name="cache_misses_total",
            description="Total Redis cache misses",
            unit="1",
        )

        self.api_key_requests_total = meter.create_counter(
            name="api_key_requests_total",
            description="Total API key authenticated requests",
            unit="1",
        )

        self.analytics_events_processed_total = meter.create_counter(
            name="analytics_events_processed_total",
            description="Total analytics events processed",
            unit="1",
        )

        self.kafka_messages_produced_total = meter.create_counter(
            name="kafka_messages_produced_total",
            description="Total Kafka messages produced",
            unit="1",
        )

        self.kafka_messages_consumed_total = meter.create_counter(
            name="kafka_messages_consumed_total",
            description="Total Kafka messages consumed",
            unit="1",
        )

        # --- Histograms ---
        self.http_request_duration_seconds = meter.create_histogram(
            name="http_request_duration_seconds",
            description="HTTP request duration in seconds",
            unit="s",
        )

        self.database_query_duration_seconds = meter.create_histogram(
            name="database_query_duration_seconds",
            description="Database query duration in seconds",
            unit="s",
        )

        self.cache_lookup_duration_seconds = meter.create_histogram(
            name="cache_lookup_duration_seconds",
            description="Redis cache lookup duration in seconds",
            unit="s",
        )

        self.kafka_latency_seconds = meter.create_histogram(
            name="kafka_latency_seconds",
            description="Kafka message end-to-end latency in seconds",
            unit="s",
        )

        # --- Up/Down Counters (Gauges) ---
        self.active_workers = meter.create_up_down_counter(
            name="active_workers",
            description="Number of active worker processes",
            unit="1",
        )

        self.pending_events_queue_depth = meter.create_observable_gauge(
            name="pending_events_queue_depth",
            description="Number of pending events in queue",
            unit="1",
            callbacks=[lambda options: []],  # Callback will be updated
        )


# Global metrics instance
metrics_instance: URLShortenerMetrics | None = None


def init_metrics():
    """Initialize global metrics instance."""
    global metrics_instance
    if not metrics_instance:
        metrics_instance = URLShortenerMetrics()
    return metrics_instance


def get_metrics() -> URLShortenerMetrics:
    if not metrics_instance:
        init_metrics()
    return metrics_instance  # type: ignore[return-value]


# Convenience functions for metric recording

def record_http_request(method: str, endpoint: str, status_code: int, duration_seconds: float, error: bool = False):
    m = get_metrics()
    attributes: dict[str, str | int] = {
        "http.method": method,
        "http.endpoint": endpoint,
        "http.status_code": status_code,
    }
    m.http_requests_total.add(1, attributes=attributes)
    m.http_request_duration_seconds.record(duration_seconds, attributes=attributes)
    if error:
        m.http_request_errors_total.add(1, attributes=attributes)


def record_url_creation(workspace_id: int, custom_alias: bool = False):
    """Record URL creation metric."""
    m = get_metrics()
    m.url_creation_total.add(1, attributes={
        "workspace_id": str(workspace_id),
        "custom_alias": str(custom_alias),
    })


def record_url_redirect(short_code: str, cache_hit: bool = False):
    """Record URL redirect (click) metric."""
    m = get_metrics()
    m.url_redirects_total.add(1, attributes={
        "short_code": short_code,
        "cache_hit": str(cache_hit),
    })


def record_cache_operation(operation: str, hit: bool, duration_seconds: float):
    """Record cache operation metric."""
    m = get_metrics()
    attributes = {
        "operation": operation,
        "hit": str(hit),
    }
    if hit:
        m.cache_hits_total.add(1, attributes=attributes)
    else:
        m.cache_misses_total.add(1, attributes=attributes)
    m.cache_lookup_duration_seconds.record(duration_seconds, attributes=attributes)


def record_api_key_request(api_key_id: int, user_plan: str):
    """Record API key authenticated request."""
    m = get_metrics()
    m.api_key_requests_total.add(1, attributes={
        "api_key_id": str(api_key_id),
        "user_plan": user_plan,
    })


def record_analytics_event(event_type: str, topic: str):
    """Record analytics event processing."""
    m = get_metrics()
    m.analytics_events_processed_total.add(1, attributes={
        "event_type": event_type,
        "topic": topic,
    })


def record_kafka_message(direction: str, topic: str):
    """Record Kafka message (produced or consumed)."""
    m = get_metrics()
    attributes = {"topic": topic}
    if direction == "produced":
        m.kafka_messages_produced_total.add(1, attributes=attributes)
    else:
        m.kafka_messages_consumed_total.add(1, attributes=attributes)


def record_database_query(query_type: str, table: str, duration_seconds: float):
    """Record database query metric."""
    m = get_metrics()
    m.database_query_duration_seconds.record(duration_seconds, attributes={
        "query_type": query_type,
        "table": table,
    })


def update_active_workers(delta: int):
    """Update active worker count."""
    m = get_metrics()
    m.active_workers.add(delta, attributes={})
