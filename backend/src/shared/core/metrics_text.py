"""Render OTel SDK metric data as Prometheus text exposition format.

``opentelemetry-sdk`` removed ``PrometheusMetricReader`` from the core SDK
(1.4x), so the Layer-1 ``/metrics`` endpoint renders the exposition here
instead. It depends only on the SDK's data model — no ``prometheus_client`` —
and works across SDK versions.

Output conventions:
  * OTel counter (monotonic Sum)  -> Prometheus ``counter``, ``_total`` suffix
  * OTel UpDownCounter / Gauge    -> Prometheus ``gauge``
  * OTel Histogram                -> ``_bucket``/``_sum``/``_count``
  * OTel ExponentialHistogram     -> skipped (not representable in this format)
  * OTel attribute keys are sanitised to ``[a-zA-Z0-9_]`` (dots/dashes -> ``_``)
"""

from __future__ import annotations

from collections.abc import Mapping

from opentelemetry.sdk.metrics.export import (
    ExponentialHistogram,
    Gauge,
    Histogram,
    MetricsData,
    Sum,
)

_HELP_ESCAPE = str.maketrans({"\\": "\\\\", "\n": "\\n"})
_LABEL_ESCAPE = str.maketrans({"\\": "\\\\", '"': '\\"', "\n": "\\n"})


def _escape_help(text: str) -> str:
    return text.translate(_HELP_ESCAPE)


def _escape_label_value(value: object) -> str:
    return str(value).translate(_LABEL_ESCAPE)


def _label_name(key: str) -> str:
    """Prometheus label names allow only [a-zA-Z_][a-zA-Z0-9_]*; OTel keys are free-form."""
    sanitized = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in key)
    if not sanitized or not (sanitized[0].isalpha() or sanitized[0] == "_"):
        sanitized = "_" + sanitized
    return sanitized


def _format_labels(attributes: Mapping[str, object] | None) -> str:
    if not attributes:
        return ""
    parts = ",".join(
        f'{_label_name(str(k))}="{_escape_label_value(v)}"'
        for k, v in sorted(attributes.items(), key=lambda kv: str(kv[0]))
    )
    return "{" + parts + "}"


def _labels_with(labels: str, extra: str) -> str:
    """Append one more label pair to an already-formatted label block."""
    if not labels:
        return "{" + extra + "}"
    return labels[:-1] + "," + extra + "}"


def _format_value(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return repr(value)


def _counter_name(name: str) -> str:
    return name if name.endswith("_total") else f"{name}_total"


def _render_histogram(lines: list[str], name: str, desc: str, data: Histogram) -> None:
    lines.append(f"# HELP {name} {_escape_help(desc)}")
    lines.append(f"# TYPE {name} histogram")
    for point in data.data_points:
        labels = _format_labels(point.attributes)
        bounds = list(point.explicit_bounds or ())
        bucket_counts = list(point.bucket_counts or ())
        cumulative = 0
        for i, bound in enumerate(bounds):
            if i < len(bucket_counts):
                cumulative += int(bucket_counts[i])
            lines.append(f"{name}_bucket{_labels_with(labels, f'le=\"{_format_value(bound)}\"')} {cumulative}")
        lines.append(f"{name}_bucket{_labels_with(labels, 'le=\"+Inf\"')} {int(point.count)}")
        lines.append(f"{name}_sum{labels} {_format_value(point.sum)}")
        lines.append(f"{name}_count{labels} {int(point.count)}")


def render_prometheus_exposition(data: MetricsData) -> str:
    """Convert a collected ``MetricsData`` snapshot to Prometheus text format."""
    if data is None:
        return "# no metric data collected\n"
    lines: list[str] = []
    for resource_metrics in data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                if not metric.data.data_points:
                    continue
                name = metric.name
                desc = metric.description or ""
                if isinstance(metric.data, Sum):
                    if metric.data.is_monotonic:
                        sample = _counter_name(name)
                        lines.append(f"# HELP {sample} {_escape_help(desc)}")
                        lines.append(f"# TYPE {sample} counter")
                        for point in metric.data.data_points:
                            lines.append(f"{sample}{_format_labels(point.attributes)} {_format_value(point.value)}")
                    else:
                        # UpDownCounter: a gauge that may go down.
                        lines.append(f"# HELP {name} {_escape_help(desc)}")
                        lines.append(f"# TYPE {name} gauge")
                        for point in metric.data.data_points:
                            lines.append(f"{name}{_format_labels(point.attributes)} {_format_value(point.value)}")
                elif isinstance(metric.data, Gauge):
                    lines.append(f"# HELP {name} {_escape_help(desc)}")
                    lines.append(f"# TYPE {name} gauge")
                    for point in metric.data.data_points:
                        lines.append(f"{name}{_format_labels(point.attributes)} {_format_value(point.value)}")
                elif isinstance(metric.data, Histogram):
                    _render_histogram(lines, name, desc, metric.data)
                elif isinstance(metric.data, ExponentialHistogram):
                    lines.append(
                        f"# (skipped {name}: ExponentialHistogram is not representable in Prometheus text format)"
                    )
    return "\n".join(lines) + "\n" if lines else "# no metrics collected\n"
