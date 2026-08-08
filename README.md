# LinkForge

Enterprise URL shortener with multi-tenant workspaces, click analytics, QR codes, webhooks, API keys, team collaboration, and an event-driven architecture.

**Live**
- Frontend: [url-shortner-peay.vercel.app](https://url-shortner-peay.vercel.app)
- Backend: [linkforge-backend-v46v.onrender.com](https://linkforge-backend-v46v.onrender.com) · Health: `GET /health`

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js, React, TypeScript, Tailwind CSS, shadcn/ui |
| **Backend** | Python 3.13, FastAPI, SQLAlchemy 2, Alembic |
| **Databases** | PostgreSQL (Neon), MongoDB, Redis (Upstash / plain) |
| **Event Bus** | Apache Kafka + Schema Registry (Aiven, Avro) |
| **Auth** | JWT (access/refresh tokens), OAuth 2.0 (Google, GitHub), Argon2 hashing |
| **Observability** | OpenTelemetry → New Relic (traces + metrics) |
| **CI/CD** | GitHub Actions, GHCR image publishing |
| **Deployment** | Render (backend), Vercel (frontend) |

---

## Features

### Core
- **URL Shortening** — Custom aliases, auto-generated short codes (Base62)
- **QR Codes** — Per-URL QR generation, bulk QR ZIP download
- **Password Protection** — Gate access with a password
- **One-Time URLs** — Self-destruct after first visit
- **A/B Testing** — Device-specific redirects (iOS / Android / default)
- **URL Expiration** — Auto-disable links at a set date/time
- **Bulk Operations** — CSV import, bulk update/disable/delete, CSV/JSON export

### Analytics
- Click count, unique visitors, device/browser/OS breakdown
- Geographic data (country, city), UTM campaign breakdown, referrer breakdown
- Daily timeseries (up to 90 days)
- Aggregated rollups updated every 60s by a dedicated worker

### Teams & Collaboration
- **Workspaces** — Multi-tenant isolation with CRUD
- **Roles** — Admin / Editor / Viewer with RBAC enforcement
- **Invites** — Email-based workspace invitations
- **Folders & Tags** — Organize URLs within workspaces

### Developer Tools
- **API Keys** — Create, revoke, rotate with per-key quota tracking (Redis daily limits)
- **Webhooks** — Subscribe to `url.clicked` events with HMAC-SHA256 signed delivery
- **Webhook Receiver** — Ingest webhooks from external services, view event history
- **Bulk API** — Programmatic CSV import/export and batch operations

### Admin
- Superadmin panel — List users/workspaces/URLs, toggle superadmin, platform-wide stats
- **Audit Logs** — Track all mutations by workspace, resource, or actor

### Security
- Argon2 password hashing
- JWT access + refresh token pair with Redis blacklisting
- Rate limiting — Token-bucket (IP-level + user-level, tiered by plan)
- RBAC middleware — Write-permission enforcement

---

## Architecture

```
                     ┌──────────────┐
                     │   Frontend   │
                     │  (Vercel)    │
                     └──────┬───────┘
                            │ HTTPS (proxied via rewrites)
                     ┌──────▼───────┐
                     │   Backend    │
                     │  (Render)    │
                     └──┬───────┬───┘
                        │       │
              ┌─────────▼──┐ ┌──▼──────────┐
              │ PostgreSQL │ │   MongoDB    │
              │  (Neon)    │ │             │
              └────────────┘ └─────────────┘
                        │
              ┌─────────▼──┐ ┌──────────────┐
              │   Redis    │ │    Kafka     │
              │ (Upstash)  │ │   (Aiven)    │
              └────────────┘ └──────┬───────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
             ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
             │  Analytics  │ │  Webhook    │ │  Metadata   │
             │   Worker    │ │  Consumer   │ │   Worker    │
             └─────────────┘ └─────────────┘ └─────────────┘
             ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
             │Aggregation  │ │   Expiry    │ │   Cleanup   │
             │   Worker    │ │   Worker    │ │   Worker    │
             └─────────────┘ └─────────────┘ └─────────────┘
             ┌──────▼──────┐ ┌──────▼──────┐
             │Webhook Retry│ │  DLQ Replay │
             │   Worker    │ │   Worker    │
             └─────────────┘ └─────────────┘
```

- **Event-driven**: Click events and URL mutations are published to Kafka (Avro-serialized) and consumed by 8 dedicated workers.
- **Multi-database**: PostgreSQL for relational data, MongoDB for click event analytics, Redis for caching/rate limiting/idempotency/quotas.
- **Resilient**: DLQ (Dead Letter Queue) for failed events, exponential backoff reconnection, scheduled workers for expiry/cleanup/aggregation.
- Workers run **embedded** in the web process by default, or **standalone** with `STANDALONE_WORKERS=1`.

---

## API Overview

All routes live under `/api/v1/` — the only exception is the redirect at `GET /{short_code}`.

| Resource | Key Endpoints |
|---|---|
| **Auth** | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`, `POST /auth/oauth/{provider}` |
| **URLs** | `GET/POST /urls`, `GET/PUT/DELETE /urls/{id}`, `GET /urls/{id}/qr` |
| **Analytics** | `GET /analytics/{short_code}/summary`, `/timeseries`, `/devices`, `/utm`, `/referrers` |
| **Workspaces** | `GET/POST /workspaces`, `POST /workspaces/{id}/invites`, `GET /workspaces/{id}/members` |
| **Webhooks** | `POST/GET /webhooks/workspace/{ws_id}`, `POST /webhook-receiver` |
| **API Keys** | `POST/GET /api-keys`, `DELETE /api-keys/{id}`, `POST /api-keys/{id}/rotate` |
| **Bulk** | `POST /urls/bulk/create`, `GET /urls/bulk/export`, `GET /urls/bulk/qr` |
| **Admin** | `POST /admin/seed`, `GET /admin/users`, `GET /admin/stats`, `PATCH /admin/users/{id}/toggle-superadmin` |
| **Other** | `GET/POST /folders`, `GET/POST /tags`, `GET/POST /favorites`, `GET /audit-logs/...`, `POST /billing/upgrade` |

Redirect: `GET /{short_code}` — 302 redirect with support for password protection, A/B testing, and device-specific URLs.

**Health**: `GET /health` returns `{"status": "healthy", "database": true, "redis": true, "kafka": true}`.

---

## Local Development

### Prerequisites
- Python 3.13+, Node.js 22+, [uv](https://docs.astral.sh/uv/), Docker (for data stores / testcontainers)

### 1. Start data stores
```bash
docker compose -f docker/docker-compose.yml up -d postgres mongodb redis
```
Docker is only used for local development — production runs on Render/Vercel without it. For the full local event pipeline, also bring up `kafka` and `schema-registry` from the same file.

### 2. Backend
```bash
cd backend
uv venv
uv sync
cp .env.example .env        # configure credentials
uv run alembic upgrade head
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000
```
Run the backend standalone (without embedded workers):
```bash
set STANDALONE_WORKERS=1
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000
```

### 3. Frontend
```bash
cd frontend
npm ci
npm run dev                 # http://localhost:3000
```
The frontend proxies `/api/*` and `/{short_code}` to the backend via Next.js rewrites.

### 4. Workers (one terminal each)
```bash
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

### 5. Enable the admin panel
```bash
curl -X POST http://localhost:8000/api/v1/admin/seed \
  -H "Authorization: Bearer <your-access-token>"
```
After bootstrapping, the first superadmin can access the Admin section in the sidebar.

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in your values. Key variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `MONGODB_URI` / `MONGODB_DB` | MongoDB for click analytics |
| `REDIS_URL` | Redis connection string (Upstash or plain) |
| `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` | Optional — used when present |
| `KAFKA_BOOTSTRAP_SERVERS` | Aiven Kafka host:port |
| `KAFKA_SASL_USERNAME` / `KAFKA_SASL_PASSWORD` | Aiven SASL credentials |
| `KAFKA_SSL_CA_PATH` | Path to `ca.pem` (local); on Render use `KAFKA_SSL_CA` with the cert contents |
| `SCHEMA_REGISTRY_URL` | Aiven Karapace schema registry |
| `SECRET_KEY` | JWT signing key (`openssl rand -hex 32`) |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth |
| `GITHUB_OAUTH_CLIENT_ID` / `GITHUB_OAUTH_CLIENT_SECRET` | GitHub OAuth |
| `OTEL_EXPORTER_OTLP_ENDPOINT` / `OTEL_EXPORTER_OTLP_HEADERS` | New Relic ingest |
| `FRONTEND_URL` / `BACKEND_URL` | Public URLs for redirects / CORS |

---

## Workers

| Worker | Trigger | Purpose |
|---|---|---|
| **Analytics** | Kafka (`url-clicked`) | Parse user-agent, store click events in MongoDB, update analytics |
| **Metadata** | Kafka (`url-created`) | Scrape title/description/OG image from destination URL |
| **Webhook Click** | Kafka (`url-clicked`) | Deliver click events to workspace webhooks with HMAC signature |
| **Webhook Retry** | Schedule (60s) | Retry failed webhook deliveries (exponential backoff, max 5 retries) |
| **DLQ Replay** | Kafka (DLQ topics) | Replay failed messages back to original topics |
| **Aggregation** | Schedule (60s) | Compute click counts and unique IPs per URL via MongoDB aggregation |
| **Cleanup** | Schedule (45s) | Purge soft-deleted URLs and associated data from all stores |
| **Expiry** | Schedule (30s) | Disable expired URLs, evict from Redis cache |

Kafka topics (created in Aiven): `url-clicked`, `url-created`, `dlq-url-clicked`, `dlq-url-created`.

---

## Testing

> **Warning:** Never run the full pytest suite against the production database. DB-backed tests truncate tables and require Docker testcontainers.

```bash
# Backend — safe without Docker (unit tests only)
cd backend && uv run pytest tests/test_core tests/test_events -q -o addopts=''

# Backend — full suite with Docker testcontainers (Postgres/Mongo/Redis)
cd backend && uv run pytest tests/ --use-testcontainers

# Frontend
cd frontend && npm run lint
cd frontend && npm run test          # Vitest unit tests
cd frontend && npm run test:e2e      # Playwright e2e tests
cd frontend && npm run test:coverage # with coverage report
```

CI runs on every push to `main` (GitHub Actions): `backend-lint`, `backend-test`, `frontend-lint`, `frontend-test`, `frontend-build`, and `docker` (builds & publishes backend/frontend images to GHCR).

---

## Deployment

### Backend — Render
Deploys from the `backend/render.yaml` blueprint. Build: `pip install uv && uv sync --no-dev`. Start: migrations then `uv run uvicorn src.main:app --host 0.0.0.0 --port $PORT`. Workers run embedded in the web service.

### Frontend — Vercel
Auto-deploys from `main`. Server-side rewrites proxy `/r/:code` and `/api/v1/*` to the Render backend via `BACKEND_URL`.

---

## License

MIT
