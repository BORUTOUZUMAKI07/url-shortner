# Full Outage

## Symptoms
- `/health` returns 503 or times out for > 30s
- Render backend reports "Timed Out" or "Exited"
- All API requests fail

## Diagnosis
1. **Port bind**: Render free tier scans port 8000; if migrations block uvicorn startup beyond the window → timeout. Check `start.sh` (migrations backgrounded) — prod uses `sh start.sh`.
2. **DB unavailable at boot**: migrations/alembic upgrade head may hang if DB unreachable. `SKIP_MIGRATIONS=1` can help in emergencies (schema assumed current).
3. **Redis/Mongo/Kafka not required to serve `/health`**: `/health` should be cheap (liveness). If it depends on external deps → regression.
4. **Container OOM**: free Render limits memory/CPU → process killed. Check logs.
5. **Collector dependency**: the app doesn't require the collector to boot; OTLP init fails open.
6. **Secret validation**: `ENVIRONMENT=production` with empty `SECRET_KEY` → ValueError at startup (prevents signing with known key). Fix env.

## Mitigation
1. **Check Render logs** for the backend service (first 200 lines of startup).
2. **Verify env vars** in Render dashboard: `SECRET_KEY` (>=32 chars), DB URLs, `OTEL_EXPORTER_OTLP_ENDPOINT` (collector or NR), `ENVIRONMENT`.
3. **If migrations blocked**: set `SKIP_MIGRATIONS=1` temporarily (schema must already be head). Revert after fixing DB.
4. **Scale up** (if OOM): move to paid tier or reduce parallelism (workers). For hobby, usually env/config.
5. **Rollback deploy**: revert to last working build.

## Verification
- `/healthz` on collector returns 200 (if deployed). Backend `/health` returns 200.
- `curl -i https://<backend>/api/v1/ping` → 200.
- Render service shows "Live".

## Notes
- `/api/v1/ping` always returns 200 (best-effort DB check) — use it for keep-warm and post-recovery sanity check.
- SIGTERM handling: workers use shutdown helpers; uvicorn signal handlers can be clobbered only if `EMBEDDED_WORKERS=1` — prod runs standalone workers typically.
