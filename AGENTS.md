# Critical Fixes

## Testcontainers — `Settings()` Rebuilt Too Early (CI "localhost:27017 refused")

**File:** `backend/tests/testcontainers.py` function `start_containers`

`config.settings` was rebuilt with `Settings()` right after `DATABASE_URL` was set, but **before** `MONGODB_URI` / `REDIS_URL` were written to the environment. pydantic-settings keeps the already-constructed defaults, so `init_mongodb()` used `mongodb://admin:adminpassword@localhost:27017` (the default) instead of the container's mapped port.

- **Locally this was masked** by a stray local MongoDB on `127.0.0.1:27017` — Mongo tests "passed" against it, not the container.
- **On GitHub runners** it failed deterministically: 5 × `pymongo.errors.ServerSelectionTimeoutError: localhost:27017: Connection refused` in `test_workers.py`.

**Fix:** set ALL of `DATABASE_URL`, `MONGODB_URI`, `REDIS_URL` (and `_USE_TESTCONTAINERS`) first, then rebuild `config.settings = Settings()` as the last step of `start_containers()`.

Related noise: `reset_pooled_engine` in `tests/test_workers.py` disposes the shared app engine whose asyncpg connections live on earlier function-scoped loops → asyncpg logs benign `RuntimeError: Event loop is closed` / "attached to a different loop" (GitHub surfaced these as 10× error annotations). The fixture suppresses the `sqlalchemy.pool` logger during dispose.

## Redis — Plain-Redis Fallback (docker-compose / local)

**File:** `backend/src/shared/core/redis.py`

`redis_client` was hard-wired to the Upstash REST client built from `UPSTASH_REDIS_REST_URL/TOKEN`; it never read `REDIS_URL`. docker-compose only sets `REDIS_URL` (plain Redis), so `/health` returned 503, cache/rate-limiting silently failed, and a `depends_on: service_healthy` on backend would hang forever.

**Fix:** `_build_redis_client()` uses the Upstash REST client when both `UPSTASH_REDIS_REST_URL` AND `UPSTASH_REDIS_REST_TOKEN` are set; otherwise it falls back to `redis.asyncio.Redis.from_url(settings.REDIS_URL, decode_responses=True)`. Both paths share the `RedisAdapter` (same `ping/get/setex/delete/incr/expire/eval` surface). Production Render sets the Upstash vars → Upstash path unchanged; compose/local get plain Redis.

## Logging — Non-root Containers Can't Create `logs/`

**File:** `backend/src/shared/logging.py` function `setup_logging`

The app runs as non-root `app` (uid 1001) on a root-owned `/app`; `log_dir.mkdir()` raised `PermissionError` and killed startup in Docker/Render.

**Fix:** Wrap the file-handler setup in `try/except OSError` → log a warning and continue with console-only logging. Docker/Render ship logs to stdout anyway.

## Migrations — Alembic Not in the Wheel, Run at Boot

**File:** `backend/Dockerfile`, `backend/entrypoint.sh`

Hatchling only packages `src/`, so `alembic/` + `alembic.ini` were absent from the wheel → fresh databases had no schema. `force-include` was rejected: it dumps the migrations at the site-packages root, colliding with the installed `alembic` package.

**Fix:** `COPY --from=builder /app/alembic /app/alembic` (and `alembic.ini`, `entrypoint.sh`) into the runtime image; `CMD ["sh", "/app/entrypoint.sh"]` runs `alembic -c alembic.ini upgrade head` then `exec uvicorn`. `SKIP_MIGRATIONS=1` disables it. Compose workers/frontend use `depends_on: backend: condition: service_healthy` so they start only after migrations complete.

## Python 3.13 SNI — Patch `wrap_bio`, not just `wrap_socket`

**File:** `backend/src/shared/workers/_sni_patch.py`

Python 3.13+ on Windows uses `ProactorEventLoop`, which calls `sslcontext.wrap_bio()` (not `wrap_socket()`) in `asyncio.ProactorEventLoop.create_connection()`. The original monkey-patch only targeted `wrap_socket`, so SNI was never injected for asyncio-managed Kafka connections. The broker received the IP address as SNI → rejected TLS handshake → `WinError 10054`.

**Fix:** When monkey-patching SSLContext for SNI, patch **both** `wrap_socket` AND `wrap_bio`:
- `_make_sni_context` now wraps both methods
- `_wrap_with_sni` decorator works for either method signature
- The `server_hostname` argument is force-injected with the bootstrap hostname, overriding whatever asyncio/aiokafka passes

```python
# Both must be patched:
sslcontext.SSLContext.wrap_socket = _wrap_with_sni(sslcontext.SSLContext.wrap_socket)
sslcontext.SSLContext.wrap_bio = _wrap_with_sni(sslcontext.SSLContext.wrap_bio)
```

## DLQ `publish_raw` — One-shot Producer

**File:** `backend/src/shared/events/kafka.py` function `publish_raw`

Workers never call `init_kafka()` so the global `producer` was `None`. DLQ messages were silently dropped.

**Fix:** When global producer is `None`, create a temporary `AIOKafkaProducer`, send the message, then stop it (`_send_and_stop`). This avoids lifecycle management across separate worker processes.

## `KeyError` for Optional Fields — Use `.get()`

**File:** `backend/src/analytics/workers/analytics_worker.py` function `process_event`

Some event fields (`original_url`, `workspace_id`, `ip_address`, `clicked_at`) might be missing in incomplete test data.

**Fix:** Use `.get()` with defaults instead of `[]` for all optional fields. Pydantic validation still catches type errors (e.g., `workspace_id` string vs int).

## Analytics Rollup — Replaced Totals Instead of Adding (counts collapsed)

**File:** `backend/src/analytics/repositories/analytics_repository.py` functions `upsert_rollup` / `upsert_click`

`upsert_rollup` did `set_={"total_clicks": total_clicks, ...}`, **replacing** the cumulative totals with only the last 60s window (the aggregation query filters `clicked_at > last_cutoff`). After 2 rollups the count collapsed. The realtime `upsert_click` also incremented the same counters → two writers with conflicting semantics.

**Fix:** the aggregation worker is now the **single writer** of the counters:
- `upsert_click` (realtime) only records `last_clicked_at` (no increments) — prevents double counting with the rollup.
- `upsert_rollup` *adds* each window to the existing totals (`URLAnalyticsSummary.total_clicks + total_clicks`).

Counters now lag up to one 60s rollup cycle instead of updating instantly.

## Avro Schemas Not Shipped — Events Silently Dropped in Production

**File:** `backend/pyproject.toml`, `backend/Dockerfile`, `backend/src/shared/events/schemas.py`

`SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schemas" / "avro"` resolves to `<site-packages>/schemas/avro` for the wheel-installed app, but the wheel only packaged `src/` and the Dockerfile didn't copy `schemas/` → `serialize()` raised `FileNotFoundError` → `url_service.py:112` swallowed it → **events silently dropped in Docker/Render** (masked locally by the editable install, which resolves to the repo root).

**Fix:** force-include the two `.avsc` files into the wheel (`[tool.hatch.build.targets.wheel.force-include]`, explicit table — comments inside an inline table are invalid TOML) and `COPY --from=builder /app/schemas /app/schemas` in the Dockerfile for editable-checkout robustness.

## Metadata Worker SSRF — User-Controlled URL Fetched Server-Side

**File:** `backend/src/webhooks/workers/metadata_worker.py` functions `extract_metadata` / `_is_safe_url`

`extract_metadata` GET'd the **user-supplied** `original_url` with `follow_redirects=True` and no IP filtering → a user could make the worker probe internal networks.

**Fix:** validate every hop before fetching — http/https schemes only, resolve the hostname with `getaddrinfo`, reject private/loopback/link-local/multicast/reserved/unspecified IPs (IPv4-mapped IPv6 unwrapped), and follow redirects manually (max 3) re-validating each hop (`follow_redirects=False`).

## Frontend Tabs — Content Never Rendered (silent dead panel)

**File:** `frontend/src/components/ui/tabs.tsx`

`TabsContent` returned `null` when `active !== value`, but `active` was only distributed via the render-prop form of `Tabs`. The analytics breakdown page (`urls/[id]/analytics/page.tsx`) passed plain children → every panel saw `active === undefined` and all 6 breakdown tabs were permanently invisible.

**Fix:** `Tabs` now also provides `active`/`setActive` via React context; `TabsTrigger`/`TabsContent` fall back to context when no explicit props are passed. Render-prop form and explicit props still work (existing tests cover both).

## Favorites N+1 — One HTTP Request Per Favorite

**File:** `frontend/src/app/(authenticated)/favorites/page.tsx`

The page fetched favorites then did `urls.get(url_id)` per favorite.

**Fix:** `GET /urls` accepts a comma-separated `ids` query param (`url_repository.get_workspace_urls` gained `url_ids`; scoped to the user's workspaces). The favorites page now does one `urls.list(null, { ids })` call and re-orders results to favorite order client-side.

# Running the Stack

## ⚠️ NEVER run the pytest suite against the production database

`backend/.env` points `DATABASE_URL` at the **production Neon DB** (free tier).
`backend/tests/conftest.py` truncates `urls, workspace_invites, workspace_members, workspaces, users`
at session start — this **wiped all real data once** when pytest was run without containers.

**Rules:**
- Never run `pytest` without `--use-testcontainers`. DB-backed tests now hard-fail without it.
- `_clean_db_once()` and the `db` fixture are guarded by `_USE_TESTCONTAINERS=1`, set only by `tests/testcontainers.py`.
- Only safe commands without Docker: `uv run pytest tests/test_core tests/test_events -q -o addopts=''`
- Always check what `.env` points at (and what session/fixture hooks do) before running anything destructive.

## Start Backend (standalone, no embedded workers)
```
cd backend
set STANDALONE_WORKERS=1
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000
```

## Start All Workers (each in own terminal)
```
cd backend
uv run python run_worker_analytics.py
uv run python run_worker_metadata.py
uv run python run_worker_webhook_click.py
uv run python run_worker_webhook_retry.py
uv run python run_worker_dlq_replay.py
uv run python run_worker_aggregation.py
uv run python run_worker_cleanup.py
uv run python run_worker_expiry.py
```

## Start Frontend
```
cd frontend
npm run dev
```

## API Base
All routes under `/api/v1/` except redirect (`/{short_code}`).

## Health
```
GET /health
GET /api/v1/auth/me
```

# When Free Trials Expire — Create New Accounts

## Aiven Kafka (30-day trial)
Update these in `.env`:
```
KAFKA_BOOTSTRAP_SERVERS=<new-host>.aivencloud.com:22283
KAFKA_SASL_USERNAME=avnadmin
KAFKA_SASL_PASSWORD=<new-password>
KAFKA_SSL_CA_PATH=./ca.pem          # Download new ca.pem from Aiven
SCHEMA_REGISTRY_URL=https://avnadmin:<new-password>@<new-host>.aivencloud.com:22275
```
Then create these topics (Aiven console or CLI):
```
url-clicked, url-created, dlq-url-clicked, dlq-url-created
```

## New Relic (free tier: 100GB/month, no expiration)
Get an ingest license key from https://one.newrelic.com/launcher/api-keys-ui.api-keys-ui
Update these in `.env`:
```
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp.nr-data.net:4318
OTEL_EXPORTER_OTLP_HEADERS=api-key=<your-ingest-license-key>
```

## No code changes needed
The app reads all credentials from env vars at runtime — including the Kafka bootstrap hostname used by `_sni_patch.py`. Just update `.env` and restart.
