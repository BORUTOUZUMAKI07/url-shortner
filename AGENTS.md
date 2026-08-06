# Critical Fixes

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
