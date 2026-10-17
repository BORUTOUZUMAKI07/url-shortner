# Runbooks Index

Operational runbooks for LinkForge. Each runbook is prescriptive, short, and includes diagnosis, mitigation, rollback, and verification.

| Runbook | When to Use | Severity |
|---|---|---|
| [High Error Rate](high-error-rate.md) | 5xx rate > 1.0% or redirect success rate < 99.9% | CRITICAL |
| [Latency SLI Burn](latency-sli-burn.md) | redirect p95 > 150ms or API p95 > 300ms | CRITICAL/WARNING |
| [Full Outage](full-outage.md) | `/health` returning 5xx/unreachable for > 30s | CRITICAL |
| [Rate Limit Exhaustion](rate-limit-exhaustion.md) | Legitimate traffic hitting 429s and backpressure growing | WARNING |
| [Redis Fail-Open](redis-fail-open.md) | Redis timeouts/pings failing but app still serving (cache degraded) | WARNING |

## General Principles

- **Fail-open**: cache/rate-limit/telemetry failures must not take the app down. Verify behavior first (don't panic over degraded paths).
- **Telemetry is best-effort**: dropped OTLP events never justify restarting DB/Redis. Check sinks (New Relic) separately.
- **Correlation IDs**: every error log carries `correlation_id`, `trace_id`, `span_id`. Search logs by correlation_id first.
- **One change at a time**: rollback recent deploys before chasing config drift.
- **Verify after every mitigation**: re-check the alert, `/health`, and a sample redirect/API call.
