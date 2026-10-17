"""
Prometheus metrics collection and tracking.
Defines all metrics used throughout the application.
"""

import functools
import re
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, TypeVar

from opentelemetry import metrics
from opentelemetry.metrics import Counter, Histogram, Observation, UpDownCounter

from src.shared import get_logger

logger = get_logger(__name__)

_F = TypeVar("_F", bound=Callable[..., Awaitable[Any]])


def _pending_events_callback(options: Any):
    """Observable callback: in-flight Kafka sends.

    Reads the producer's ``_pending_sends`` set directly (the authoritative
    "queued for delivery" count). Imported lazily inside the callback so the
    metrics module does not import the Kafka layer at import time (kafka.py
    imports this module). Fails open: an empty observation beats a broken
    metrics export.
    """
    try:
        from src.shared.events import kafka as kafka_module

        return [Observation(len(kafka_module._pending_sends))]
    except Exception:
        return []



class URLShortenerMetrics:
    """Collection of all application metrics."""

    # Counters (monotonically increasing)
    http_requests_total: Counter
    http_request_errors_total: Counter
    url_creation_total: Counter
    url_redirects_total: Counter
    cache_hits_total: Counter
    cache_misses_total: Counter
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
            description="Kafka events queued for delivery (in-process producer)",
            unit="1",
            callbacks=[_pending_events_callback],
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


def record_url_creation(custom_alias: bool = False):
    """Record URL creation metric.

    Deliberately *not* labelled by ``workspace_id``: workspace count is
    unbounded, so that label would create a time series per workspace.
    """
    m = get_metrics()
    m.url_creation_total.add(1, attributes={"custom_alias": str(custom_alias)})


def record_url_redirect(cache_hit: bool = False):
    """Record URL redirect (click) metric.

    Deliberately *not* labelled by ``short_code``: one time series per link is
    exactly the cardinality explosion that makes metrics unusable.
    """
    m = get_metrics()
    m.url_redirects_total.add(1, attributes={"cache_hit": str(cache_hit)})


def record_cache_operation(operation: str, hit: bool, duration_seconds: float, layer: str = ""):
    """Record cache operation metric.

    ``layer`` distinguishes an L1 (in-process) hit from a Redis round trip —
    the whole point of having an L1 at all.
    """
    m = get_metrics()
    attributes = {
        "operation": operation,
        "hit": str(hit),
        "layer": layer,
    }
    if hit:
        m.cache_hits_total.add(1, attributes=attributes)
    else:
        m.cache_misses_total.add(1, attributes=attributes)
    m.cache_lookup_duration_seconds.record(duration_seconds, attributes=attributes)


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


def record_kafka_consume(topic: str, timestamp: Any):
    """Record one consumed Kafka message: count it and its e2e latency.

    ``timestamp`` is the producer's CreateTime, which aiokafka exposes either
    as epoch milliseconds (int) or a ``datetime`` depending on version, so both
    shapes are accepted. A non-positive/absurd latency (clock skew) is dropped
    rather than recording a nonsense sample.
    """
    record_kafka_message("consumed", topic)
    if timestamp is None:
        return
    try:
        if isinstance(timestamp, datetime):
            produced_at = timestamp
            if produced_at.tzinfo is None:
                produced_at = produced_at.replace(tzinfo=timezone.utc)
        elif isinstance(timestamp, (int, float)):
            # Epoch ms (>1e12) vs epoch s — ms is the Kafka wire format.
            seconds = timestamp / 1000 if timestamp > 1e12 else float(timestamp)
            produced_at = datetime.fromtimestamp(seconds, tz=timezone.utc)
        else:
            return
        latency = (datetime.now(timezone.utc) - produced_at).total_seconds()
    except (OverflowError, OSError, ValueError):
        return
    if 0 <= latency < 86400:
        get_metrics().kafka_latency_seconds.record(latency, attributes={"topic": topic})


def record_database_query(query_type: str, duration_seconds: float):
    """Record database query metric.

    Only the *operation* (SELECT/INSERT/…) is labelled — not the table — so the
    series count stays bounded regardless of schema growth.
    """
    m = get_metrics()
    m.database_query_duration_seconds.record(duration_seconds, attributes={
        "query_type": query_type,
    })


def update_active_workers(delta: int):
    """Update active worker count."""
    m = get_metrics()
    m.active_workers.add(delta, attributes={})


def track_worker(func: _F) -> _F:
    """Count a worker entry coroutine in the ``active_workers`` gauge.

    ``main.py`` starts these coroutines as embedded asyncio tasks and the
    ``run_worker_*.py`` scripts call them directly; both go through this
    wrapper, so the gauge reflects embedded and standalone deployments alike.
    """

    @functools.wraps(func)
    async def _wrapper(*args: Any, **kwargs: Any) -> Any:
        update_active_workers(1)
        try:
            return await func(*args, **kwargs)
        finally:
            update_active_workers(-1)

    return _wrapper  # type: ignore[return-value]


# --- SQLAlchemy query-duration metrics -------------------------------------
#
# Wired from `shared.core.database` at engine creation, so the web process and
# every worker get them. The app is async, so two executions can be in flight
# on one thread: the start timestamp is stored on the per-statement
# ExecutionContext rather than in a thread-local (which would let one query
# overwrite another's start time mid-flight).

_SQL_OPERATIONS = frozenset({
    "SELECT", "INSERT", "UPDATE", "DELETE", "BEGIN", "COMMIT", "ROLLBACK",
    "AUTOCOMMIT", "SAVEPOINT", "RELEASE", "CREATE", "ALTER", "DROP",
    "TRUNCATE", "SHOW", "SET", "EXPLAIN", "CALL", "VALUES",
})
_SQL_OPERATION_RE = re.compile(r"\s*(?P<op>[A-Za-z_]+)")
_STARTED_AT_ATTR = "_linkforge_query_started_at"

# Idempotent per engine: listeners fire once per statement, so installing them
# twice would record every query twice.
_installed_db_metric_engines: set[int] = set()


def query_operation(statement: Any) -> str:
    """First keyword of a SQL statement, bounded to a fixed vocabulary.

    Never the table: one label per table is a time series per table, and
    schema changes would silently create new series.
    """
    if not isinstance(statement, str):
        return "unknown"
    match = _SQL_OPERATION_RE.match(statement)
    if not match:
        return "unknown"
    operation = match.group("op").upper()
    return operation if operation in _SQL_OPERATIONS else "other"


def install_db_query_metrics(engine: Any) -> None:
    """Record query durations through SQLAlchemy's cursor events.

    Attached here rather than to the OTel instrumentor so it works in every
    process that owns a engine (app + the six workers) and stays independent
    of trace sampling. Best-effort: a listener this module cannot install is a
    missing metric, never a startup failure.
    """
    key = id(engine)
    if key in _installed_db_metric_engines:
        return
    _installed_db_metric_engines.add(key)
    try:
        from sqlalchemy import event

        target = getattr(engine, "sync_engine", engine)

        @event.listens_for(target, "before_cursor_execute")
        def _record_start(conn, cursor, statement, parameters, context, executemany):
            try:
                setattr(context, _STARTED_AT_ATTR, time.perf_counter())
            except Exception:
                pass

        @event.listens_for(target, "after_cursor_execute")
        def _record_end(conn, cursor, statement, parameters, context, executemany):
            started = getattr(context, _STARTED_AT_ATTR, None)
            if started is None:
                return
            try:
                setattr(context, _STARTED_AT_ATTR, None)
            except Exception:
                pass
            record_database_query(query_operation(statement), time.perf_counter() - started)

        logger.debug("DB query metrics installed on %s", type(target).__name__)
    except Exception as e:
        _installed_db_metric_engines.discard(key)
        logger.warning("DB query metrics not installed: %s", e)

