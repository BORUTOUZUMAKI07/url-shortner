# LinkForge — Enterprise URL Shortener

Full-stack URL shortening platform with multi-tenant workspaces, click analytics, QR codes, webhooks, API keys, and an event-driven architecture.

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui |
| **Backend** | Python 3.13, FastAPI, SQLAlchemy 2, Alembic |
| **Databases** | PostgreSQL 16, MongoDB 7, Redis 7 |
| **Event Bus** | Apache Kafka, Avro schemas, Karapace Schema Registry |
| **Workers** | 8 background workers (analytics, metadata, aggregation, expiry, cleanup, webhooks, DLQ replay) |
| **Observability** | OpenTelemetry, Prometheus, Grafana, Loki, Jaeger |
| **Testing** | Vitest (frontend), Playwright (e2e), MSW (API mocking), Pytest (backend) |
| **CI/CD** | GitHub Actions (9 jobs), Trivy security scan, GHCR |

## Quick Start

```bash
# Start all services (data stores + app + workers + observability)
cd docker
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3001 |
| Backend API | http://localhost:8000 |
| Kafka UI | http://localhost:8080 |
| Grafana | http://localhost:3000 (admin/admin) |
| Jaeger | http://localhost:16686 |

## Local Development

```bash
# 1. Start infrastructure (Postgres, MongoDB, Redis, Kafka)
docker compose up postgres mongodb redis kafka

# 2. Backend
cd backend
uv venv && source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows
uv sync
cp .env.example .env                 # configure credentials
alembic upgrade head
uvicorn src.main:app --reload --port 8000

# 3. Frontend
cd frontend
npm ci
npm run dev                           # http://localhost:3000
```

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start Next.js dev server |
| `npm run test` | Run frontend unit tests |
| `npm run test:e2e` | Run Playwright e2e tests |
| `npm run lint` | ESLint check |
| `cd backend && uvicorn src.main:app` | Start backend |
| `cd backend && pytest` | Run backend tests |

## Architecture

- **Event-driven**: Click events and URL mutations are published to Kafka and consumed by dedicated workers for analytics, webhook delivery, expiry, and cleanup.
- **Multi-tenant**: Workspaces with RBAC, each isolated.
- **Testing layers**: Unit tests per component/service, integration tests for routes and event flows, e2e tests with Playwright, MSW for API mocking.

## Deployment

The project is configured for Koyeb and GitHub Container Registry. CI publishes Docker images to `ghcr.io` on version tags.
