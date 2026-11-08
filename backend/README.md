# LinkForge — Backend

FastAPI-based URL shortening service with Kafka event streaming, multi-database storage, and embedded background workers.

## What It Does

The backend is the API and business-logic layer for LinkForge. It handles:

- **Auth**: register/login, JWT access + refresh tokens, OAuth 2.0 (Google, GitHub), password reset, `HttpOnly` cookie sessions
- **URLs**: create/read/update/delete short links, password protection, expiration, custom aliases, QR codes, A/B device targeting, one-time links
- **Redirects**: `GET /{short_code}` — L1 cache → Redis → PostgreSQL, with SSRF-safe metadata resolution off the hot path
- **Workspaces**: multi-tenant isolation with roles (admin/editor/viewer), invites, members
- **Analytics**: click ingestion to MongoDB, cumulative rollups to PostgreSQL every 60s
- **Webhooks**: outbound delivery with HMAC-SHA256 signatures, retry + dead-letter queue
- **API Keys**: create/revoke/rotate with per-key daily quota (Redis atomic counters)
- **Admin**: superadmin panel, audit logs, user/workspace/URL listing

## Architecture

### Layers

```
backend/src/
├── main.py              # FastAPI app, middleware, lifespan (starts 8 workers)
├── shared/              # Cross-cutting: config, DB, Redis, Mongo, security, events, workers
│   ├── core/
│   │   ├── config.py         # pydantic-settings (env → config, validators)
│   │   ├── database.py       # SQLAlchemy async engine + session factory
│   │   ├── security.py       # Argon2 hashing, JWT create/decode
│   │   ├── redis.py          # Redis client (Upstash or plain, fail-open)
│   │   ├── mongodb.py        # Motor + Beanie async Mongo init
│   │   ├── client_ip.py      # Single X-Forwarded-For resolver (rightmost when TRUST_PROXY)
│   │   ├── geo_service.py    # IP→location, async, public-IP only (off redirect path)
│   │   ├── api_key_auth.py   # API-key auth + quota helpers
│   │   └── base.py           # SQLAlchemy declarative Base + naming convention
│   ├── events/               # Kafka: dispatcher, producer, Avro schemas
│   ├── middleware/           # Audit context, metrics, security headers
│   ├── errors/               # AppError hierarchy → HTTP status codes
│   └── workers/              # Kafka consumer pool + shutdown helpers
├── admin/          # Superadmin panel, audit logs
├── analytics/      # Click rollups, timeseries, watermarks
├── identity/       # Auth, JWT, OAuth, sessions, API keys
├── links/          # URL CRUD, redirect, QR, A/B
├── webhooks/       # Subscriptions, delivery, DLQ
├── workspaces/     # Multi-tenancy, invites, members
└── scripts/        # Maintenance: e2e_server.py, purge_users.py
```

### Data Flow (Redirect)

```
Browser → Next.js frontend → FastAPI /{short_code}
                                │
                                ├─► L1 cache (in-process, 10s TTL)
                                ├─► Redis cache (~10–50ms)
                                └─► PostgreSQL (50–200ms on miss)
                                │
                                ▼
                           302 Redirect to destination
                                │
                                └─► Publish url-clicked to Kafka
                                      └─► Analytics worker: parse UA, geo, write MongoDB
                                            └─► Aggregation worker: rollup to Postgres every 60s
```

### Workers (8, embedded in the web process by default)

| Worker | Trigger | Purpose |
|---|---|---|
| analytics | Kafka `url-clicked` | Parse user-agent + geo, write click events to MongoDB |
| metadata | Kafka `url-created` | Fetch page title/OG image (SSRF-guarded) |
| webhook_click | Kafka `url-clicked` | Deliver click events to workspace webhooks |
| webhook_retry | Schedule (60s) | Retry failed webhook deliveries (exponential backoff, max 5) |
| dlq_replay | Kafka DLQ topics | Replay failed messages back to original topics |
| aggregation | Schedule (60s) | Aggregate MongoDB clicks into PostgreSQL rollups |
| expiry | Schedule | Mark expired links |
| cleanup | Hourly | Hard-delete soft-deleted URLs after 30-day grace |

Workers run as `asyncio` tasks inside uvicorn (single worker, fits Render free tier). Set `STANDALONE_WORKERS=1` + `run_worker_*.py` scripts to run them as separate processes.

## Database Schema

See [`docs/database-schema.md`](../docs/database-schema.md) for the full ER diagram, table catalog, indexes, and on-delete behavior.

Tables: `users`, `api_keys`, `workspaces`, `workspace_members`, `workspace_invites`, `urls`, `folders`, `tags`, `url_tags`, `favorites`, `url_analytics_summary`, `aggregation_watermarks`, `webhooks`, `webhook_subscriptions`, `webhook_events`, `webhook_received_events`, `audit_logs`, `dead_letter_events`.

## Local Development

### Prerequisites
- Python 3.13+, [uv](https://docs.astral.sh/uv/), Docker (for data stores / testcontainers)

### 1. Start data stores
```bash
docker compose -f ../docker/docker-compose.yml up -d postgres mongodb redis
# Full event pipeline:
docker compose -f ../docker/docker-compose.yml up -d kafka schema-registry
```

### 2. Backend
```bash
cd backend
uv venv
uv sync
cp .env.example .env        # configure credentials (see .env.example)
uv run alembic upgrade head
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Run standalone (no embedded workers):
```bash
set STANDALONE_WORKERS=1
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000
```

### 3. Workers (one terminal each)
```bash
cd backend
uv run python run_worker_analytics.py
uv run python run_worker_metadata.py
uv run python run_worker_webhook_click.py
uv run python run_worker_webhook_retry.py
uv run python run_worker_dlq_replay.py
uv run python run_worker_aggregation.py
```

### 4. Enable the admin panel
Set `ADMIN_BOOTSTRAP_TOKEN` in `backend/.env` (any random 32+ char string). The endpoint is disabled with a 404 while empty.
```bash
openssl rand -hex 32  # generate token
# add ADMIN_BOOTSTRAP_TOKEN=<token> to backend/.env

curl -X POST http://localhost:8000/api/v1/admin/seed \
  -H "Authorization: Bearer <your-access-token>" \
  -H "X-Admin-Bootstrap-Token: <ADMIN_BOOTSTRAP_TOKEN>"
```

## Environment Variables

Copy `backend/.env.example` to `backend/.env`.

| Variable | Purpose | Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@localhost:5432/db` |
| `MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017/db` |
| `MONGODB_DB` | MongoDB database name | `linkforge` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `UPSTASH_REDIS_REST_URL` / `TOKEN` | Optional Upstash Redis | used when present |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka host:port | `localhost:9092` |
| `KAFKA_SASL_USERNAME` / `PASSWORD` | Kafka SASL credentials | Aiven |
| `KAFKA_SSL_CA_PATH` | Path to `ca.pem` | local dev |
| `SCHEMA_REGISTRY_URL` | Schema registry URL | `http://localhost:8081` |
| `SECRET_KEY` | JWT signing key | `openssl rand -hex 32` |
| `GOOGLE_OAUTH_CLIENT_ID` / `SECRET` | Google OAuth | |
| `GITHUB_OAUTH_CLIENT_ID` / `SECRET` | GitHub OAuth | |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector endpoint | `http://localhost:4318` |
| `OTEL_EXPORTER_OTLP_HEADERS` | OTLP headers | vendor auth |
| `FRONTEND_URL` / `BACKEND_URL` | Public URLs for redirects / CORS | |
| `ADMIN_BOOTSTRAP_TOKEN` | Admin panel bootstrap token | |
| `ENVIRONMENT` | `development`/`production` | guards blank SECRET_KEY in prod |
| `STANDALONE_WORKERS` | `1` to run workers as separate processes | |
| `TRUST_PROXY` | `true` behind a proxy (Render) | trusts X-Forwarded-For |

## Testing

> Warning: Never run the full pytest suite against the production database. DB-backed tests truncate tables and require Docker testcontainers.

```bash
# Safe without Docker (unit tests only)
uv run pytest tests/test_core tests/test_events -q -o addopts=''

# Full suite with Docker testcontainers (Postgres/Mongo/Redis)
uv run pytest tests/ --use-testcontainers

# Lint + types
uv run ruff check src/ tests/ scripts/
uv run mypy src/
```

## Deployment

### Render (production)
Deploys from `backend/render.yaml`. Build: `pip install uv && uv sync --no-dev`. Start: migrations then `uv run uvicorn src.main:app --host 0.0.0.0 --port $PORT`. Workers run embedded in the web service.

Managed services: Neon (Postgres), Upstash (Redis), Aiven (Kafka), MongoDB — free tiers.

## Project Structure

```
backend/
├── alembic/              # DB migrations (versioned schema)
├── src/
│   ├── admin/            # superadmin, audit logs
│   ├── analytics/        # click rollups, timeseries
│   ├── identity/         # auth, JWT, OAuth, sessions, API keys
│   ├── links/            # URL CRUD, redirect, QR, A/B
│   ├── shared/           # config, DB, Redis, security, events, workers
│   ├── webhooks/         # subscriptions, delivery, DLQ
│   └── workspaces/       # multi-tenancy, invites, members
├── scripts/              # e2e_server.py, purge_users.py
├── tests/                # unit, route, core, event tests
├── render.yaml           # Render blueprint
├── pyproject.toml        # Python deps (uv)
└── README.md             # this file
```

## License

MIT
