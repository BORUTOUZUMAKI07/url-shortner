# High Error Rate

## Symptoms
- NR alert: `high_http_5xx_error_rate` (>1.0% for 5m)
- NR alert: `redirect_success_rate_low` (<99.9% for 10m)
- `/health` may still return 200 (process healthy, upstream failing)

## Quick Diagnosis (2–5 min)
1. **Scope**: check which route templates are emitting 5xx (exclude `/health`, `/api/v1/ping`).
2. **Recent changes**: inspect last Render/backend deploy (git SHA) and config/env diffs.
3. **Dependencies**: check DB (Neon) connectivity, Redis (Upstash/container), MongoDB, Kafka brokers (Aiven/compose). All can be slow after idle (Neon cold start).
4. **Logs**: search for `level=ERROR` with `service=url-shortener` in New Relic Logs (or local logs). Filter by `correlation_id` from failing requests.
5. **Sentry** (if configured): scan for new error groups — they often explain a spike.

## Common Causes
- **DB cold start** (Neon free tier idle → first queries slow → timeouts → 5xx). Fix: keep-warm `/api/v1/ping` helps; temporarily increase timeouts not recommended.
- **Redis Upstash blips** (TLS reconnects) — cache is fail-open but quota/rate-limit Lua scripts can throw; Redis failures are caught per call.
- **Kafka unavailability** (lifecycle events become best-effort; don't 5xx on produce).
- **Bad config**: missing env vars causing exceptions at import/runtime.
- **SQLAlchemy dead connections**: fixed by `pool_pre_ping`/`pool_recycle` — verify recent deploys didn't regress.

## Mitigation
1. **Rollback** (fastest): revert to last known-good commit on Render backend.
2. **Scale/readiness**: if DB cold-start dominates, run a warm-up (hit `/api/v1/ping` repeatedly) — often self-resolves in 1–3 min.
3. **Throttle traffic** (if flooding): temporarily block abusive IPs via WAF/rate-limit tuning (careful with shared buckets).
4. **Fix root cause**: address the specific exception (from Sentry/New Relic error trace), redeploy.
5. **No panic over telemetry**: OTLP 401s/503s won't cause 5xx on request paths (exporters fail-open).

## Verification
- Alert clears after 1m under threshold.
- Sample `curl -v https://<backend>/api/v1/ping` returns 200 (no DB-dependent logic).
- Sample redirect returns 302/404/410 as expected (no new 5xx).
- New Relic error count returns to baseline.

## Rollback Checklist
- [ ] Identify bad commit (git blame + Render deploy history)
- [ ] `git revert` + push to trigger Render rebuild
- [ ] Monitor for 5–10 min post-deploy
- [ ] Document incident + fix in commit/issue
