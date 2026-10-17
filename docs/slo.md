# LinkForge SLOs

This document defines service level objectives (SLOs) and indicators (SLIs) for LinkForge (url-shortner). Targets are intentionally conservative for a hobby deployment while still protecting the critical user path (redirects).

## Critical User Path: Short Code Redirects `GET /{short_code}`

Redirects are the only revenue/traffic-critical path. They must be fast and serve 3xx with near-zero avoidable errors.

| SLI | Measurement | Target (SLO) | Error Budget (30d) |
|---|---|---|---|
| Availability | % of redirect requests returning 3xx (300-399) | ≥ 99.9% | 0.1% (~43 min) |
| Latency (p95) | Time to first byte / total request duration p95 | ≤ 150ms | Breach if > 150ms for 5m sustained |
| Latency (p99) | p99 redirect duration | ≤ 250ms | Warning (soft) |

## Non-Redirect API Paths

All other `api/v1/*` endpoints. Lower latency budget than redirects (they do more work, auth, DB, events).

| SLI | Measurement | Target (SLO) | Notes |
|---|---|---|---|
| Availability | % of requests returning 2xx/3xx (exclude 4xx client errors from "server error" SLI) | ≥ 99.5% | 4xx (400/401/403/404/409) excluded from error budget |
| Latency (p95) | p95 request duration | ≤ 300ms | Breach if > 300ms for 10m sustained |

## Telemetry/Data Pipeline (Best-Effort)

The analytics/event pipeline is **best-effort** (see AGENTS.md "Events are best-effort"). It has no user-facing SLO. We only alert on *backpressure causing request-time impact* (queue depth → 5xx on request paths), never on dropped events alone.

## Telemetry Volume & Quota (Scaling)

All LinkForge telemetry (logs, metrics, traces) leaves the app through the
collector's single `otlphttp/newrelic` exporter to `https://otlp.nr-data.net:4318`
(see `docker/otel-collector-config.yaml`). The New Relic free grant is ~100 GB/month,
so **the first wall at 10× traffic is vendor ingest quota, not application
capacity** — and the failure mode is silent by design: every exporter is
fail-open, so once the quota is exhausted telemetry is dropped while the app keeps
serving 3xx. Nothing in the SLO tables above catches that, because it is a
*vendor* metric, not an app one.

Volume knobs, in the order they should be turned:

| Knob | Where | Default | Effect |
|---|---|---|---|
| `OTEL_TRACES_SAMPLE_RATIO` | app (`shared/core/config.py`) | `1.0` | Fraction of spans emitted. Leave at 1.0 while the collector is in front — let tail-sampling decide, since the app has no view of the whole trace. Lower it only when pushing straight to a vendor. |
| `tail_sampling` policies | collector | all errors + latency > 2000 ms + 10% of the rest | Sheds volume while keeping the spans that explain incidents. This is the primary lever. |
| `batch.timeout` / `send_batch_size` | collector | 5 s / 512 | Coalesces many small OTLP calls into few large ones — matters more than sampling at steady, high volume. |
| `sending_queue.queue_size` | collector | 1000 | Burst smoothing only; in-memory and deliberately not durable. |

Two things follow:

- **Alert on quota at the vendor.** The usage metric lives in New Relic, so
  configure a data-usage alert there (e.g. 70% of the monthly grant) rather than
  expecting the app to notice. There is no app-side signal to alert on.
- **Attribute usage per project.** `service.name` / `service.namespace` are
  stamped on every signal, so if this New Relic account is shared with the
  sibling projects (same US ingest endpoint), usage can be split per project
  before deciding who trims sampling.

## Alerting Alignment

- **Critical**: redirect availability < 99.9% (10m) OR redirect p95 > 150ms (5m)
- **Warning**: general API p95 > 300ms (10m), 5xx rate > 1.0% (5m)
- **Recovery**: alerts auto-resolve when metrics return under threshold for 1m

## Notes

- `/health` and `/api/v1/ping` are excluded from request latency/error SLOs (liveness probes).
- High-cardinality labels are avoided in alerting NRQL (route template used, not raw path).
- 5xx includes network/DB/Redis/Kafka integration failures. 429s (rate limited) are client-side backpressure and **excluded** from the server-error SLI.
- SLO compliance is measured against New Relic Metrics (OTLP) with a 30-day rolling window.
