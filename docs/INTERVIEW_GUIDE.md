# LinkForge — Interview Preparation Guide

> Everything we built, every tool we chose, every bug we fixed — written the way you explain it in an interview.
> Read this before any interview. It is written as if you know nothing, so every concept is explained in plain words first.

---

## How to use this file

1. **Part 1 — The project in plain words** (what you built and why it matters)
2. **Part 2 — Tool dictionary** (every tool, explained simply, with "why we chose it")
3. **Part 3 — Architecture walkthrough** (how the pieces talk to each other)
4. **Part 4 — STAR stories** (every major step: **S**ituation, **T**ask, **A**ction, **R**esult). These are your interview answers.
5. **Part 5 — One-sentence answers** (quick revision cheat sheet)
6. **Part 6 — Likely interview questions**

---

# PART 1 — The project in plain words

LinkForge is an **enterprise-grade URL shortener**. A URL shortener takes a long link like
`https://example.com/very/long/path?utm_source=newsletter` and returns a short link like `https://short.ly/Ab3xQ9`.
When someone visits the short link, they are redirected to the original long link.

But this is NOT a beginner URL shortener. It adds:

- **Accounts & auth** — register, login, Google/GitHub OAuth, password reset, refresh tokens stored in `HttpOnly` cookies.
- **Workspaces (multi-tenant teams)** — teams of users with roles (viewer / editor / admin / owner) sharing links.
- **Analytics** — every click records device, browser, operating system, geography, referrer, UTM parameters.
- **QR codes, password-protected links, expiring links, custom aliases, folders, tags, favorites, bulk CSV import/export.**
- **Webhooks** — when a URL is clicked or created, external services can be notified.
- **API + API keys** — programmatic access with rate limiting.
- **Observability** — traces, metrics, and logs sent to New Relic.
- **Event-driven background processing with Kafka** — heavy work (analytics, webhooks) does NOT happen in the web request; it happens asynchronously in separate worker processes.

The stack: **FastAPI (Python) backend + Next.js (React/TypeScript) frontend + PostgreSQL + MongoDB + Redis + Apache Kafka**, deployed on **Render** free tier with **GitHub Actions** CI.

---

# PART 2 — Tool dictionary

Every tool we used, why we picked it, and the plain-words explanation.

## Backend

| Tool | What it is (plain words) | Why we chose it |
|---|---|---|
| **Python 3.13** | Programming language. | Huge ecosystem, great for async, easy to hire for. |
| **FastAPI** | Python web framework. | Async-native (handles many concurrent requests without blocking), automatic OpenAPI docs at `/docs`, **Pydantic** validation built in (type-safe request/response). Compared to Flask/Django: async + auto-docs + type hints. |
| **Uvicorn** | ASGI server that actually runs FastAPI. | The standard async server for FastAPI. |
| **SQLAlchemy 2.0** | ORM — maps Python classes to database tables. | Mature, supports **async** with the `asyncpg` driver, lets us use the Repository pattern. |
| **asyncpg** | Async PostgreSQL driver. | Never blocks the event loop during database queries (critical for a high-traffic API). |
| **Alembic** | Database migration tool (works with SQLAlchemy). | Version-controlled schema changes — the database schema evolves with the code, not manually. |
| **Pydantic v2 + pydantic-settings** | Validation + config from environment variables. | Request validation and `.env`-driven config (`settings.DATABASE_URL`, etc.). |
| **MongoDB + Motor** | NoSQL document database + async driver. | Analytics click-events are high-volume and unstructured; Mongo handles this better than Postgres. `Motor` gives us an async driver. |
| **Redis** | In-memory key-value store. | Super-fast cache for short-code → URL lookups, rate limiting counters, refresh-token blacklist. |
| **Apache Kafka (managed by Aiven)** | Distributed message broker (a "queue on steroids"). | Decouples the web API from heavy background work. Events are **durable** (survive crashes) and support **consumer groups** (multiple workers). |
| **aiokafka** | Async Python client for Kafka. | Async-native Kafka producer/consumer. |
| **OpenTelemetry** | Vendor-neutral tracing/metrics instrumentation. | One API that sends traces/metrics to New Relic. Also instrumented FastAPI, Redis, SQLAlchemy. |
| **uv** | Super-fast Python package/venv manager. | Way faster than pip + venv, single tool. |
| **ruff** | Fast Python linter + import sorter. | Catches bugs/style issues; enforces import order in CI. |
| **mypy** | Static type checker. | Catches type errors before runtime; runs in CI. |
| **pytest + pytest-asyncio** | Test framework + async test support. | Unit and integration tests, including async handlers. |
| **testcontainers** | Spins up real Docker containers (Postgres/Mongo/Redis) for tests. | Tests run against **real databases** in CI instead of mocks — catches real integration bugs. |
| **httpx** | HTTP client. | Used in tests to hit the API via `ASGITransport` (in-process, no network). |
| **hashids** | Library that encodes numbers into short unique strings. | Generating short codes for URLs. |
| **user-agents** | Library to parse User-Agent strings. | Extract device/browser/OS from a click for analytics. |
| **ipinfo.io** | IP geolocation API. | Resolve click IP → country/city for analytics. |
| **passlib/bcrypt** | Password hashing. | Store only hashes, never plaintext passwords. |

## Frontend

| Tool | Why |
|---|---|
| **Next.js (App Router, "use client")** | React framework with SSR/SSG, routing, and a built-in proxy layer. |
| **TypeScript** | Type safety across the whole frontend. |
| **Tailwind CSS** | Fast utility-first styling. |
| **react-hook-form + zod** | Form state management + schema validation. |
| **zustand** | Tiny, fast global state store (auth state). |
| **motion (framer-motion)** | Animations. |
| **lucide-react** | Icons. |
| **vitest** | Fast unit tests for the frontend. |
| **eslint + tsc** | Code quality + type checks in CI. |

## Infra / Deploy / CI

| Tool | Why |
|---|---|
| **Docker + docker-compose** | Local stack that matches production (Postgres, Mongo, Redis, Kafka all in one command). |
| **Render (free tier)** | Deployment. Free web service + free Postgres/Redis/managed DBs. |
| **Neon** | Serverless PostgreSQL (free tier). Production Postgres. |
| **Upstash** | Serverless Redis (free tier). Production Redis. |
| **Aiven** | Managed Kafka (30-day free trial). Production Kafka. |
| **GitHub Actions** | CI/CD — runs on every push to `main`. 6 parallel jobs: Backend Tests, Backend Lint (ruff+mypy), Frontend Build, Frontend Test, Frontend Lint, Docker Build (pushes images to GHCR). |
| **GHCR** | GitHub Container Registry — stores Docker images. |
| **New Relic** | Observability backend (free tier). Receives OTel traces/metrics. |
| **AGENTS.md** | Repo file that documents critical fixes and operational rules (e.g., "never run pytest against production"). It's our institutional memory — a good practice to mention in interviews. |

---

# PART 3 — Architecture walkthrough

## Plain-words mental model

```
User clicks short link
        │
        ▼
┌────────────────────────────┐
│  Next.js frontend (browser)│
└────────────┬───────────────┘
             │ HTTPS
             ▼
┌────────────────────────────┐        ┌──────────────────────────┐
│  FastAPI backend  (1 proc) │        │  PostgreSQL (Neon)        │
│  - auth, urls, workspaces  │◄──────►│  users, urls, workspaces, │
│  - redirect /{short_code}  │        │  webhooks, audit, summary │
│  - embedded/worker tasks   │        └──────────────────────────┘
└──────┬──────────────┬──────┘        ┌──────────────────────────┐
       │              │               │  Redis (Upstash)         │
       │  publish     │  read/write   │  cache, rate limit,      │
       ▼              ▼               │  refresh-token blacklist │
┌──────────────┐  ┌──────────┐        └──────────────────────────┘
│  Kafka       │  │ MongoDB  │        ┌──────────────────────────┐
│ url-clicked  │  │ click     │        │  8 background workers    │
│ url-created  │◄─┤ events,   │        │  analytics, aggregation, │
│ dlq topics   │  │ timeseries│        │  webhooks, metadata,     │
└──────────────┘  └──────────┘        │  expiry, cleanup, dlq     │
                                      └──────────────────────────┘
```

Key idea: **the web API never does slow work inline.** When a link is clicked:
1. Redis cache is checked; if miss, Postgres is queried.
2. The user is redirected immediately (fast).
3. A `url-clicked` event is **published to Kafka**.
4. A separate **worker** consumes that event, parses the user-agent, resolves geolocation, writes to MongoDB, triggers webhooks, and later aggregation rolls up totals into Postgres.

If the analytics worker crashes, **redirects still work** — the events wait safely in Kafka (within retention).

## The 8 workers

| Worker | What it does |
|---|---|
| analytics_worker | Consumes `url-clicked`, parses device/browser/OS/geo, writes to MongoDB, touches `URLAnalyticsSummary.last_clicked_at` in realtime. |
| aggregation_worker | Periodically aggregates MongoDB click events into `URLAnalyticsSummary` in Postgres. **Single writer for the click counters** — its `upsert_rollup` *adds* each window to the existing totals (incremental), never replaces them, so cumulative counts can't collapse or double-count with the realtime path. |
| metadata_worker | Consumes `url-created`, fetches page title/metadata — **SSRF-guarded** (http/https only, no auto-redirects, resolves each hop and rejects private/loopback/reserved IPs). |
| webhook_click_consumer | On clicks, delivers webhooks to external subscribers. |
| webhook_retry_worker | Retries failed webhook deliveries. |
| dlq_replay_worker | Consumes dead-letter-queue topics and retries them. |
| expiry_worker | Marks expired links. |
| cleanup_worker | Deletes stale data (old refresh tokens, etc.). |

In production, these run as `asyncio` tasks inside the same FastAPI process (to stay inside Render free tier memory). They can also run as fully separate processes via `STANDALONE_WORKERS=1` and `run_worker_*.py` scripts.

## API routes (all under `/api/v1/`)

- `/api/v1/auth/me`, `/register`, `/login`, OAuth flows
- `/api/v1/urls`, `/bulk`, `/favorites`, `/folders`, `/tags`, `/redirect`
- `/api/v1/workspaces`, invites, members, roles
- `/api/v1/webhooks/workspace/{id}/...`, `/api/v1/analytics`, `/api/v1/audit-logs`, `/api/v1/admin`
- `/{short_code}` (public redirect, outside `/api/v1`)

---

# PART 4 — STAR stories

Every story follows **Situation → Task → Action → Result**. These are your actual interview answers. Practise saying them out loud.

---

## STORY 1 — Tests hit `localhost:27017` instead of the test database (CI bug)

**Situation:** Our test suite uses **testcontainers** — it spins up real PostgreSQL, MongoDB, and Redis in Docker, then points the app at them via environment variables. Locally, tests seemed to pass. On GitHub CI, 5 tests failed deterministically with `pymongo.errors.ServerSelectionTimeoutError: localhost:27017: Connection refused`.

**Task:** Figure out why CI couldn't reach the MongoDB container and fix it.

**Action:**
- I read `tests/testcontainers.py`, which starts the containers and then rebuilds the app config.
- Found the bug: the code wrote `DATABASE_URL` to the environment and then immediately did `Settings()`. But `MONGODB_URI` and `REDIS_URL` were written **after** the `Settings()` rebuild.
- `pydantic-settings` only reads env vars **once**, at construction time. So the app was created with default values (`mongodb://admin:adminpassword@localhost:27017`) instead of the container's mapped port.
- Locally this was masked by a stray local MongoDB running on `127.0.0.1:27017` — tests were "passing" against the wrong database.
- Fix: set **all** env vars (`DATABASE_URL`, `MONGODB_URI`, `REDIS_URL`, `_USE_TESTCONTAINERS`) first, then rebuild `Settings()` **as the last step**.

**Result:** CI tests now connect to the real containers. This taught us: **never assume env-dependent config is read lazily — pydantic-settings reads once.**

---

## STORY 2 — `asyncpg` connections reused across event loops (116 CI failures)

**Situation:** After enabling the new middleware, CI exploded with 116 failures: `asyncpg.exceptions.InterfaceError: cannot perform operation: another operation is in progress`. Locally the same code passed.

**Task:** Find why asyncpg connections were being shared across test runs and fix it.

**Action:**
- I learned that **pytest-asyncio gives each test a fresh event loop**.
- `asyncpg` connections are **bound to the event loop that created them** (thread/loop affinity). Reusing a pooled connection from a different loop causes that error.
- Root cause: the new `rbac.py` and `rate_limit.py` middleware did `from src.shared.core.database import AsyncSessionLocal` at **module import time**. That bound the **global engine with a connection pool** (`pool_size=20`) before tests replaced `AsyncSessionLocal` with a `NullPool` version. So the middleware used the global pooled engine, and pooled asyncpg connections were reused across event loops.
- Fix: change the middleware to `from src.shared.core import database` and call `database.AsyncSessionLocal()` **at request time**, so the test patch is respected and each test gets a fresh connection.

**Result:** The asyncpg cascade disappeared. Lesson: **import-time side effects are dangerous — defer engine/session creation to call time.**

---

## STORY 3 — Redis hard-wired to Upstash, broke docker-compose (health 503)

**Situation:** `/health` reported `redis: false` and rate limiting silently failed when running via docker-compose, which only sets `REDIS_URL` (a plain Redis).

**Task:** Make Redis work with both Upstash (production) and plain Redis (local/CI).

**Action:**
- Found `redis_client` was built **only** from `UPSTASH_REDIS_REST_URL/TOKEN`, ignoring `REDIS_URL`.
- Rewrote `_build_redis_client()`: if **both** Upstash vars are set → use the Upstash REST client (production path, unchanged). Otherwise → fall back to `redis.asyncio.Redis.from_url(settings.REDIS_URL)`.
- Both paths share the same `RedisAdapter` interface (`ping/get/setex/delete/incr/expire/eval`), so no caller changes.

**Result:** `/health` is green in both environments. Lesson: **don't hard-wire external services to one vendor; read config and provide a fallback.**

---

## STORY 4 — Non-root container can't create `logs/` (startup crash)

**Situation:** The app crashed on startup in Docker/Render: `PermissionError` when creating a `logs/` directory. The container runs as non-root user `app` (uid 1001) on a root-owned `/app`.

**Task:** Stop the crash without weakening container security.

**Action:**
- Wrapped the file-handler setup in `setup_logging()` in `try/except OSError`.
- On failure, log a warning and continue with **console-only logging** (Docker/Render ship stdout to logs anyway).

**Result:** App starts everywhere. Lesson: **make filesystem features degrade gracefully in restricted environments.**

---

## STORY 5 — Database migrations missing from the built image (fresh DBs had no schema)

**Situation:** The Python package build tool (Hatchling) only packages `src/`, so `alembic/` and `alembic.ini` were **not** in the deployed wheel. Fresh databases had zero tables.

**Task:** Get migrations into production and run them before the app starts.

**Action:**
- Tried `force-include` in Hatchling — rejected, because it dumped migrations at the site-packages root and collided with the installed `alembic` package.
- Fix in the Dockerfile: `COPY --from=builder /app/alembic /app/alembic` plus `alembic.ini` and `entrypoint.sh` into the runtime image.
- `CMD ["sh", "/app/entrypoint.sh"]` runs `alembic -c alembic.ini upgrade head` then `exec uvicorn`. `SKIP_MIGRATIONS=1` disables it.
- Compose workers/frontend use `depends_on: backend: condition: service_healthy` so they only start after migrations complete.

**Result:** Fresh databases get the full schema automatically at boot.

---

## STORY 6 — Python 3.13 SNI bug on Windows (Kafka TLS handshake failed)

**Situation:** On Windows (Python 3.13) with asyncio + Aiven Kafka (TLS), connections failed with `WinError 10054`. A monkey-patch injecting the SNI hostname existed but didn't work.

**Task:** Fix TLS SNI injection for asyncio-managed Kafka connections on Python 3.13.

**Action:**
- Learned that Python 3.13 on Windows uses `ProactorEventLoop`, which calls **`sslcontext.wrap_bio()`**, not `wrap_socket()`, inside `create_connection()`.
- The existing patch only covered `wrap_socket`, so SNI was never injected — the broker received the raw IP as SNI and rejected the handshake.
- Fix: patch **both** `wrap_socket` and `wrap_bio`, force-injecting the bootstrap hostname as `server_hostname`.

**Result:** Kafka TLS works on Windows dev. Lesson: **"works in prod" ≠ "works everywhere" — platform event-loop differences matter.**

---

## STORY 7 — Dead-letter-queue messages were silently dropped

**Situation:** Workers never call `init_kafka()`, so the global Kafka `producer` was `None`. DLQ (dead-letter-queue) messages were silently dropped.

**Task:** Ensure DLQ publishes always send, even from worker processes.

**Action:**
- In `publish_raw`, when the global producer is `None`, create a **temporary one-shot** `AIOKafkaProducer`, send the message, then stop it (`_send_and_stop`).
- This avoids managing producer lifecycle across separate worker processes.

**Result:** Failed messages always land in the DLQ topics (`dlq-url-clicked`, `dlq-url-created`) and can be replayed by `dlq_replay_worker`.

---

## STORY 8 — `KeyError` on optional event fields

**Situation:** Analytics worker crashed with `KeyError` when event payloads were missing optional fields (`original_url`, `workspace_id`, `ip_address`, `clicked_at`).

**Task:** Make the worker resilient to incomplete data without losing type safety.

**Action:**
- Replaced direct indexing with `.get()` + defaults for all optional fields in `process_event`.
- Pydantic validation still catches wrong types (e.g., `workspace_id` string vs int).

**Result:** Worker survives partial/malformed events.

---

## STORY 9 — Tracing middleware broken after FastAPI startup rebuild

**Situation:** OpenTelemetry instrumentation of FastAPI stopped working — the middleware that instruments routes was created **before** FastAPI rebuilt its middleware stack during startup, so it was discarded.

**Task:** Keep OTel middleware alive across the startup rebuild.

**Action:**
- Moved `instrument_fastapi` (and Redis/SQLAlchemy instrumentation) to run **inside** the app lifespan, after FastAPI's own startup, so the instrumented middleware survives.

**Result:** Traces/metrics flow to New Relic correctly. Lesson: **FastAPI rebuilds its middleware stack at startup — instrument after that.**

---

## STORY 10 — RBAC middleware authorized writes in a separate DB session (24 CI failures)

**Situation:** After adding middleware-level RBAC ("viewers must not write"), CI showed 24 failures — bulk and webhook tests getting `403 Requires editor role or higher.` on valid requests.

**Task:** Make role enforcement correct in both tests and production.

**Action:**
- Diagnosed: the middleware opened its **own** DB session to check roles. In tests, fixture data lives in the request's session **inside an open transaction** — a second session cannot see uncommitted rows, so it denied valid requests. In production it also meant **two DB round-trips per write request**.
- Investigated the service layer: url/folder/tag/bulk/webhook services already enforce editor+ via `verify_role` using the **request's own session**; the workspace service enforces owner/admin checks via `verify_access`.
- Decision: **remove the middleware's DB checks entirely** and rely on the service layer — the security guarantee (viewers can't write) is preserved, tests see fixture data, and we cut a redundant DB call per request.

**Result:** 24 failures → 0. CI green. Lesson: **authorization belongs at the operation boundary where the transaction lives, not in a side session.**

---

## STORY 11 — Workspace owner could be locked out by a viewer membership row

**Situation:** `verify_role` checked memberships **first** and fell back to the owner only if no membership existed. An owner who also had a `viewer` membership row would be **denied** editor operations — a latent lockout bug.

**Task:** Decide the correct rule and make code + tests agree.

**Action:**
- The sane rule: **the owner always retains full access** regardless of any membership row.
- Reordered `verify_role` to check `Workspace.owner_id` first and return `True`.
- Updated `test_require_role_viewer_denied_for_editor` to use a real **non-owner** viewer (preserving its intent: viewers can't edit), and added `test_require_role_owner_always_allowed` to pin the new rule.

**Result:** Owners can never be locked out; viewers still can't write. CI green.

---

## STORY 12 — HttpOnly cookie migration (security)

**Situation:** Access/refresh tokens were stored in `localStorage` on the frontend — vulnerable to XSS (any injected script could steal them).

**Task:** Move tokens out of JavaScript's reach.

**Action:**
- Backend sets tokens in **`HttpOnly`** cookies (`SameSite=Lax`, secure in prod) — JavaScript cannot read them, so XSS can't exfiltrate them.
- Frontend: removed all `localStorage` token usage; `api.ts` refreshes via cookie (`credentials: "include"`); OAuth flow uses a `refresh_token` query param fed to `auth.refresh()`; deleted `token-cookie.ts` and its tests.
- Explicit CORS origins (browsers reject `*` with credentials).

**Result:** Token theft via XSS is no longer possible. This is a classic security story to tell.

---

## STORY 13 — CI/CD pipeline journey (the debugging arc)

**Situation:** We wanted every push to `main` to be validated by CI and every deploy to be reproducible.

**Task:** Build a CI pipeline that catches real bugs.

**Action:**
- GitHub Actions workflow with **6 parallel jobs**: Backend Tests (testcontainers), Backend Lint (ruff + mypy), Frontend Build, Frontend Tests, Frontend Lint, and Docker Build (pushes images to GHCR).
- Learned to surface failures well: failing-test summaries as **error annotations**, and test logs uploaded as **artifacts** on failure (this is how we diagnosed the testcontainers and asyncpg bugs).
- Iterated through several red CI runs (testcontainers config, ruff import order, asyncpg loop bug, RBAC 403s) until everything was green.
- Render auto-deploys from the Docker image on every push.

**Result:** Every commit is verified end-to-end. This story shows debugging discipline — good to tell.

---

## STORY 14 — Deploying a heavy app on Render free tier

**Situation:** Render free tier gives **512 MB RAM**, sleeps after 15 minutes of inactivity, and has no free background workers.

**Task:** Run a Kafka-driven, multi-database app within those limits.

**Action:**
- **Single worker**: `uvicorn src.main:app --host 0.0.0.0 --port $PORT` (default = 1 worker) to stay under 512 MB.
- **Embedded workers**: the 8 Kafka/scheduled workers run as `asyncio` tasks inside the same process (with `STANDALONE_WORKERS=1` as the escape hatch for running them as separate processes).
- **Migrations at boot**: entrypoint runs `alembic upgrade head` before `exec uvicorn`.
- **Health endpoint** `/health` checks database, redis, kafka — used by Render and by uptime pings.
- Managed services: Neon Postgres, Upstash Redis, Aiven Kafka, MongoDB — free tiers keep memory off the web instance.

**Result:** The whole stack runs on free tier. Mention the tradeoffs honestly in interviews (cold starts, sleep, Kafka consumer reconnection).

---

## STORY 15 — "Should we split into microservices?" (the design decision)

**Situation:** The codebase is event-driven (Kafka) and modular. Someone suggested splitting into a `core-service` and an `analytics-service`.

**Task:** Decide if a microservices split is worth it.

**Action:**
- I evaluated honestly. A monorepo *can* host multiple deployable services — that's standard. But I mapped the proposed split against the real code:
  - Only **2 of 8** workers are analytics; the other 6 (webhooks, metadata, expiry, cleanup, DLQ) need Postgres.
  - The **aggregation worker writes analytics summaries into Postgres** — so "analytics owns MongoDB only" was false; a clean split forces a decision on where that data lives.
  - Render free tier: two services = twice the memory (each ~300 MB boots FastAPI+Kafka+SQLAlchemy+PyMongo) and **two services that sleep** and disconnect Kafka consumers.
  - Conclusion: **stay a modular monolith**, and get the one real microservice benefit (fault isolation) as a **deployment** change — run the analytics workers as a separate Render web service with a dummy `/health` when needed, since workers already run as separate processes.

**Result:** No rewrite. This is a strong "senior" story: showing you can say *no* to over-engineering with concrete evidence.

---

## STORY 16 — Webhook events junction table

**Situation:** Webhooks stored events as a list (unstructured) — hard to query and validate.

**Task:** Normalize event subscriptions.

**Action:** Introduced a **junction table** (`webhook_events`) between webhooks and event types, with `CHECK` constraints, so each webhook subscribes to explicit events.

**Result:** Data integrity enforced at the database level.

---

## STORY 17 — Modular monolith restructure

**Situation:** Code was scattered; tests were risky (one session actually truncated production data once).

**Task:** Make the codebase domain-organized and make tests safe.

**Action:**
- Restructured into **domain folders** (`identity`, `links`, `workspaces`, `analytics`, `webhooks`, `admin`) each with `routes / services / repositories / models / workers`.
- Added hard guards: DB-backed tests **refuse to run** without `--use-testcontainers`, and cleanup only runs when `_USE_TESTCONTAINERS=1` — so the test suite can never touch the production `.env` database again.

**Result:** Clean, navigable codebase and safe tests.

---

## STORY 18 — Kafka worker reliability hardening

**Situation:** Two reliability bugs: `init_kafka()` wasn't idempotent (leaked producers in embedded workers) and `/health` showed a stale Kafka status.

**Task:** Make Kafka lifecycle reliable.

**Action:**
- Made `init_kafka` idempotent (guard against re-init).
- `/health` now imports the Kafka **module** and checks live state instead of a cached boolean.

**Result:** Stable workers and accurate health checks.

---

## STORY 19 — One-time links: race condition on consume (TOCTOU)

**Situation:** "One-time" links are links that can be visited exactly once — the second visit returns 404. The original implementation did a read-then-write: `SELECT active → UPDATE active=0`. Two simultaneous clicks could both pass the check and both redirect, burning the link twice.

**Task:** Make the consume atomic so exactly one request wins.

**Action:**
- Replaced the read-then-write with a **single conditional UPDATE**: `UPDATE urls SET active=0 WHERE id=:id AND active=true`.
- The rowcount tells us the winner: 0 rows updated → someone else already consumed it → raise `URLNotFound`.

**Result:** One winner only, no locks, no transactions spanning multiple statements. This is a classic **atomic compare-and-swap** pattern — good to explain.

---

## STORY 20 — OAuth refresh token rode the callback URL (leaked in logs/referrer)

**Situation:** The Google/Refresh OAuth callback passed the provider **refresh token** as a `?code=` query parameter in the redirect to the frontend. That token landed in browser history, server access logs, and the Referer header of any subsequent navigation — a genuine credential leak.

**Task:** Move the token off the URL without breaking the OAuth flow.

**Action:**
- The callback now writes a **one-time handoff code** to Redis (TTL 120s) and redirects to `/login?code=<handoff>` — the code is worthless outside the next minute.
- The frontend calls `POST /auth/oauth/exchange` with that code; the server swaps it for a session inside a POST body (never in a URL).
- The old `refresh_token` query-param flow was removed from both `api.ts` and the login page.

**Result:** The refresh token never appears in URLs, logs, or Referer headers. Strong security story — same pattern as CSRF tokens and short-lived grants.

---

## STORY 21 — API-key quota was defined but never enforced (dead code)

**Situation:** We had a `verify_api_key_quota` function and a per-user daily limit concept, but the function was **never called** from the API-key authentication path — quota enforcement was silently dead code.

**Task:** Actually enforce the daily quota without blocking API requests.

**Action:**
- Wired `verify_api_key_quota(api_key_id, user_plan)` into the API-key branch of `get_current_user`, so every API-key request checks quota.
- Implemented it with an **atomic Redis Lua script** (`CHECK_AND_INCREMENT`) — increment the counter, compare to `daily_limit`, return over/under in one round-trip (no check-then-set race).
- Added an in-process `dict` fallback for when Redis is unavailable, so the API degrades gracefully instead of erroring.
- Chose a non-blocking counter (increment-and-compare) rather than a token bucket per request — burst limits are still enforced, but we don't maintain per-key token state.

**Result:** Quota is enforced in production with one atomic Redis op per request.

---

## STORY 22 — Analytics counts collapsed (rollup replaced totals instead of adding)

**Situation:** Cumulative click counts were **collapsing** — after two rollup cycles the totals were wrong. The 60s aggregation query only looks at events newer than the last cutoff, but `upsert_rollup` **replaced** the stored totals with that one window instead of adding to them. Meanwhile the realtime path was also incrementing the same counters → two writers with conflicting semantics.

**Task:** Make the counters correct and monotonic.

**Action:**
- Made the aggregation worker the **single writer** of the counters.
- Realtime `upsert_click` now only records `last_clicked_at` — no increments (it was double-counting with the rollup).
- `upsert_rollup` **adds** each window to the existing totals instead of replacing them.

**Result:** Counters are cumulative and correct, lagging at most one 60s cycle. Good story about **two writers = conflicting semantics**.

---

## STORY 23 — Geo lookup moved off the redirect hot path

**Situation:** Every redirect resolved the visitor's IP synchronously via the geo service — that meant a geoip2 lookup (DNS/IP-stack latency) on **every click**, in the request path the whole product exists to keep fast.

**Task:** Keep geolocation in the analytics while removing it from the redirect.

**Action:**
- Moved geo resolution into `analytics_worker.process_event` — the async consumer that already parses the click — so it happens off the request path.
- Added `GeoService._is_public_ip()`: reject private/loopback/link-local/multicast/reserved/unspecified IPs and unwrap IPv4-mapped IPv6 before resolving, so internal topology can never be recorded.

**Result:** Redirects are fast again; geo still lands in analytics. Two lessons: **never do slow I/O in a hot path** and **never geolocate/record internal addresses**.

---

## STORY 24 — Polling workers didn't shut down gracefully (data loss on SIGTERM)

**Situation:** `KeyboardInterrupt`/`CancelledError` escaped the asyncio loops in the polling workers (aggregation, cleanup, expiry, webhook retry) and the Kafka consumer pool — dirty exits, partial batches, and noisy logs. Separately, `close_kafka()` stopped the producer immediately, **aborting messages still in the flush queue**.

**Task:** Make shutdown clean and lossless.

**Action:**
- Standardized all polling workers on the shared `shared.workers.shutdown` helpers: `install_signal_handlers()` + `wait_for_shutdown()` with `asyncio.wait_for(asyncio.shield(...))`.
- The consumer pool re-raises `CancelledError`, shields `consumer.stop()` in `finally`, and re-raises on backoff-sleep cancellation.
- `kafka.py` now tracks in-flight sends in `_pending_sends`; `close_kafka()` awaits them (10s cap) before stopping the producer.

**Result:** Clean shutdowns, no dropped in-flight messages.

---

## STORY 25 — Hot-path indexes missing (full scans on every auth/listing/expiry query)

**Situation:** `api_keys.prefix`, `urls.workspace_id`, `urls.expires_at`, and `webhook_events.status` had no indexes — API-key authentication, workspace URL listing, expiry scans, and webhook retry queries all did table scans.

**Task:** Index the hot paths without breaking the migration chain.

**Action:**
- New Alembic migration `f5e6d7c8b9a0` (parent `f490c0f533a4`) creating `ix_api_keys_prefix`, `ix_urls_workspace_id`, `ix_urls_expires_at`, `ix_webhook_events_status`.
- Kept the models in sync with `index=True` so future `alembic revision --autogenerate` won't drift.

**Result:** FK/status/expiry lookups hit indexes. Lesson: **watch for implicit `WHERE` clauses on columns you never thought of as "search" columns.**

---

# PART 5 — One-sentence answers (cheat sheet)

- **What is this project?** An enterprise URL shortener with auth, workspaces, analytics, webhooks, and an API, built on FastAPI + Next.js + PostgreSQL + MongoDB + Redis + Kafka.
- **Why FastAPI?** Async by default (handles concurrent I/O without blocking) + automatic OpenAPI docs + Pydantic type-safe validation.
- **Why Kafka instead of doing work inline?** Slow work (analytics, webhooks) would slow every click; Kafka makes work durable, asynchronous, retryable, and isolated.
- **Why MongoDB for analytics?** High-volume, unstructured click events and time-series aggregations fit a document store better than a relational table.
- **Why Redis?** Microsecond caching for short-code→URL lookups, rate limiting, and refresh-token blacklist.
- **Why SQLAlchemy + asyncpg?** ORM productivity with a true async Postgres driver so queries never block the event loop.
- **Why testcontainers?** Tests should run against *real* databases, not mocks — it caught the `localhost:27017` bug mocks never would.
- **Why did we drop the RBAC middleware?** It authorized writes in a separate DB session (2 round-trips per request, invisible-to-transaction data). The service layer already enforces roles using the request's own session, so the middleware was redundant.
- **How do workers stay up on Render free tier?** They run as asyncio tasks inside the one uvicorn process (single worker to fit 512 MB); `STANDALONE_WORKERS=1` runs them as separate processes.
- **Did you consider microservices?** Yes — and rejected it: only 2 of 8 workers are analytics, the aggregation worker writes to Postgres (boundary leaks), and free tier can't afford two 300 MB instances. Modular monolith + optional deployment split is the right call.
- **How do you keep tests from touching production?** Hard guards: DB tests fail without `--use-testcontainers`, and session cleanup runs only when `_USE_TESTCONTAINERS=1`.
- **What was the hardest bug?** The asyncpg cross-event-loop pooling bug: 116 CI failures caused by module-import-time engine binding. Fixed by deferring session creation to request time.
- **How do one-time links stay one-time?** Atomic conditional UPDATE (`SET active=0 WHERE active=true`) + rowcount check — no read-then-write race (Story 19).
- **Why a one-time OAuth handoff code?** The refresh token used to ride the callback URL (logs/history/referrer leak); now Redis holds a 120s handoff code exchanged via POST (Story 20).
- **Is the API-key quota enforced?** Yes — it was dead code, now wired into `get_current_user` via an atomic Redis `CHECK_AND_INCREMENT` Lua script with an in-process fallback (Story 21).
- **Why does the aggregation worker write the counters?** Two writers (realtime increments + rollup replace) corrupted totals; now one writer *adds* each window and the realtime path only records `last_clicked_at` (Story 22).
- **Why is geolocation async?** It used to run on every redirect; now the analytics worker resolves it off the hot path and only for public IPs (Story 23).
- **How do workers shut down cleanly?** Shared `wait_for_shutdown` helpers with shielded timeouts; Kafka drains in-flight sends before `producer.stop()` (Story 24).
- **Why new indexes?** `api_keys.prefix`, `urls.workspace_id`, `urls.expires_at`, `webhook_events.status` were scanned on every auth/listing/expiry/retry query (Story 25).

---

# PART 6 — Likely interview questions

1. **"Walk me through this project."** → Parts 1 + 3, then one STAR story of your choice (pick Story 2, 10, or 15 — they show the most depth).
2. **"Why did you choose these technologies?"** → Part 2.
3. **"Tell me about a hard bug."** → Story 2 (asyncpg) or Story 1 (testcontainers) or Story 6 (SNI) or Story 19 (TOCTOU race).
4. **"How do you ensure code quality?"** → CI with ruff + mypy + unit/integration tests, testcontainers, linting, PR review.
5. **"How do you keep data safe in tests?"** → Story 17 (hard guards, `--use-testcontainers`).
6. **"Have you ever over-engineered something?"** → Story 15 (microservices) — and mention you know when NOT to build microservices.
7. **"How would you scale this?"** → Separate the analytics workers into their own service (Story 15), add more Kafka partitions/consumer groups, cache more aggressively, move to a paid Render/cloud tier, add a CDN for redirects.
8. **"What would you do next?"** → Uptime pinger for the free-tier sleep, Redis write-through on redirects, webhook idempotency keys, feature branches + PRs.
9. **"Tell me about a security fix you made."** → Story 12 (HttpOnly cookies), Story 20 (OAuth handoff), or the metadata-worker SSRF guard (AGENTS.md).

---

# PART 7 — File-by-file map ("what does this file do?")

Use this when an interviewer says *"walk me through your codebase"* or when you are studying.
The pattern everywhere is: **routes → services → repositories → models**. Routes parse HTTP, services hold business logic + authorization, repositories do database queries, models define tables.

## Backend — `backend/src/`

### Entry point
| File | What it does |
|---|---|
| `main.py` | The FastAPI app. `create_app()` wires middleware, exception handlers, `/health`, routers, and the **lifespan** which starts the 8 background workers (unless `STANDALONE_WORKERS=1`). |

### `shared/` — cross-cutting everything uses
| File | What it does |
|---|---|
| `core/config.py` | `Settings` (pydantic-settings) — all environment variables, with defaults. Rebuilt once at startup (this caused the testcontainers bug in Story 1). |
| `core/database.py` | SQLAlchemy async **engine**, `AsyncSessionLocal` factory, `init_db()`, health check. |
| `core/base.py` | Declarative `Base` with a metadata **naming convention** (no shared model fields). |
| `core/base_repository.py` | Generic CRUD (`get`, `get_by`, `get_many`, `create`, `update`, `delete`) every repository inherits, plus unit-of-work ops (`commit`, `rollback`, `flush`) and admin queries (`count`, `list_all`). |
| `core/security.py` | Password hashing (argon2), JWT create/decode for access + refresh tokens. |
| `core/redis.py` | `RedisAdapter` and `_build_redis_client()` — chooses Upstash or plain Redis (Story 3). |
| `core/mongodb.py` | Async Mongo init via Motor + Beanie (no health check here). |
| `core/click_event.py` | MongoDB `ClickEvent` model only (`URLAnalyticsSummary` lives in `analytics/models/analytics.py`). |
| `core/deps.py` | FastAPI dependencies: `get_db` (session per request), `get_current_user`, plus service factories. The API-key branch of `get_current_user` calls `verify_api_key_quota` on every request (Story 21). |
| `core/rbac.py` | `check_role` — core role-hierarchy helper. |
| `core/api_key_auth.py` | API-key auth + quota helpers (`authenticate_api_key`, `verify_api_key_quota`) — standalone, not a FastAPI dependency. |
| `core/geo_service.py` | IP → location resolution (ipinfo.io), Redis-cached. `_is_public_ip()` rejects private/loopback/link-local/reserved IPs and unwraps IPv4-mapped IPv6 — resolved **async in the analytics worker**, off the redirect hot path (Story 23). |
| `core/user_plan.py` | `UserPlanResolver` abstraction + `DatabaseUserPlanResolver` (opens a session at call time, caches the user's plan for 60s). |
| `core/base62.py` | Base62 encoding used for short codes. |
| `core/metrics.py`, `core/tracing.py` | OpenTelemetry metrics + tracing init/instrumentation (OTel API, not the Prometheus client). |
| `core/event_dispatcher.py`, `events/dispatcher.py`, `events/schemas.py` | Event publishing plumbing (`EventDispatcher`) + Avro schema serialize/deserialize/register. The `.avsc` files live in `backend/schemas/avro` and are force-included into the wheel (`pyproject.toml`) + copied in the Dockerfile, so serialization works in the installed image. |
| `events/kafka.py` | Kafka **producer** helpers only (`init_kafka`, `publish_event`, `publish_raw` with the one-shot fallback from Story 7); consumers live in `workers/kafka_consumer_pool.py`. |
| `errors/*.py` | Error classes (`AppError` base, auth/common/url/workspace) → HTTP status codes. |
| `logging.py` | `setup_logging()` — console + file handler with graceful fallback (Story 4). |
| `middleware/audit.py` | `AuditContextMiddleware` — attaches audit context to requests. |
| `middleware/metrics.py` | `MetricsMiddleware` — request metrics. |
| `middleware/rate_limit.py` | `RateLimitMiddleware` — Redis-based rate limiting; the user-plan lookup goes through an injected `UserPlanResolver` (sessions opened at call time, Story 2 fix). |
| `middleware/rbac.py` | Only `require_role` helper now (middleware class removed, Story 10). |
| `middleware/tracing.py` | `TracingMiddleware` — OTel request tracing (Story 9). |
| `workers/_sni_patch.py` | SNI monkey-patch for Python 3.13 Windows Kafka TLS — patches `wrap_socket` AND `wrap_bio` (Story 6). |
| `workers/kafka_consumer_pool.py` | Kafka consumer pool with connection backoff. |
| `workers/shutdown.py` | Graceful shutdown helpers. |

### `identity/` — auth & users
| File | What it does |
|---|---|
| `models/user.py`, `models/api_key.py` | User and ApiKey tables. |
| `repositories/user_repository.py`, `api_key_repository.py` | User/API-key DB queries. |
| `services/auth_service.py` | Register, login, refresh, logout, forgot/reset password, email verification, OAuth init/callback (`create_oauth_handoff` / `exchange_oauth_handoff` swap the provider token for a 120s Redis handoff code — Story 20); returns JWT pairs (HttpOnly cookies are set in `routes/auth.py`, Story 12). |
| `services/api_key_service.py` | Create/list/revoke/rotate API keys + daily-quota lookups. |
| `services/email_service.py` | Verification, password-reset, and workspace-invite emails. |
| `services/sso/google_oauth.py`, `github_oauth.py` | OAuth2 login flows. |
| `services/profile_service.py` | Change password/email, upload avatar (verifies the current password via `UserRepository`). |
| `routes/auth.py`, `routes/profile.py`, `routes/api_keys.py` | HTTP endpoints under `/api/v1/auth`, `/profile`, `/api-keys` (profile handlers call `ProfileService`). |
| `schemas/*.py` | Request/response validation models. |

### `links/` — the URL core
| File | What it does |
|---|---|
| `models/url.py` | URL table — short_code, original_url, status, expiry, optional password. (UTM params are parsed at click time, not stored.) |
| `models/folder.py`, `models/tag.py`, `models/favorite.py` | Folder, tag, favorite tables. |
| `services/url_service.py` | Create/update/delete URLs; `_verify_write_role(editor+)`; cache invalidation; publishes events. Session-free — the `URLRepository` owns the transaction (`create_url`/`commit`/`rollback`/`next_short_code`). |
| `services/redirect_service.py` | Resolves a short code → redirect; records the click; publishes `url-clicked`. Geo is resolved async in the analytics worker (Story 23); one-time links consume via atomic conditional UPDATE + rowcount → `URLNotFound` (Story 19). |
| `services/bulk_service.py` | Bulk create/update/disable/reactivate/delete/export + QR zip (with role checks). Session-free — row inserts go through `url_repo.add_nested()` (SAVEPOINT per row); final commit via `url_repo.commit()`. |
| `services/folder_service.py`, `tag_service.py`, `favorite_service.py`, `utm_service.py` | Domain logic for folders/tags/favorites; `utm_service` is just a query-string parser (utm_source/medium/campaign) that enriches click events. |
| `routes/urls.py`, `redirect.py`, `bulk.py`, `folders.py`, `tags.py`, `favorites.py` | HTTP endpoints (`redirect.py` is the public `/{short_code}` 302, mounted at app root). `GET /urls` also accepts an `ids` query param so the favorites page can bulk-load its URL list in one request (no N+1). |
| `workers/expiry_worker.py`, `workers/cleanup_worker.py` | Background jobs: expire links (disable + evict cache); purge soft-deleted URLs and their click/analytics data. |

### `workspaces/` — multi-tenant teams
| File | What it does |
|---|---|
| `models/workspace.py`, `models/workspace_member.py`, `models/workspace_invite.py` | Workspace, membership (with `MemberRole` + `ROLE_HIERARCHY`), invites. |
| `repositories/workspace_repository.py` | `verify_access` (owner-or-member), `verify_role` (owner-first, Story 11), `get_user_workspaces`, `create_default`. |
| `repositories/workspace_member_repository.py`, `workspace_invite_repository.py` | Membership/invite queries. |
| `services/workspace_service.py` | Create, rename, delete, invite, accept invite, change roles, remove members — with owner/admin checks (Story 10). |
| `routes/workspaces.py` | HTTP endpoints. |

### `webhooks/` — external notifications
| File | What it does |
|---|---|
| `models/webhook.py`, `models/webhook_event.py`, `models/webhook_subscription.py`, `models/webhook_received_event.py` | Webhook config, **outbound delivery log** (`webhook_events`), **subscription junction** (webhook↔event type), inbound received-events log. |
| `repositories/webhook_repository.py` | Owns the transactions: `create_with_subscriptions`, `sync_subscriptions`, `record_delivery`. |
| `services/webhook_service.py` | Webhook CRUD + `_verify_write_role`; secret encrypt/decrypt, subscription sync, and `deliver_event` (HMAC-signed POST) — depends only on repositories, not the session. |
| `services/webhook_receiver_service.py` | **Inbound** receiver — verifies HMAC signature on incoming deliveries, logs them to `webhook_received_events`. |
| `routes/webhooks.py`, `routes/webhook_receiver.py` | Management endpoints + public `POST /webhook-receiver` (HMAC-verified inbound) + authenticated `GET /webhook-receiver/events/{workspace_id}`. |
| `workers/webhook_click_consumer.py`, `webhook_retry_worker.py`, `metadata_worker.py`, `dlq_replay_worker.py` | Kafka consumer → HMAC delivery (Story 16); 60s DB poller retrying failed deliveries → Postgres DLQ; page-metadata fetcher (title/description/og:image); Kafka DLQ topic replayer. |

### `analytics/` — click analytics
| File | What it does |
|---|---|
| `models/analytics.py`, `models/audit_log.py`, `models/dead_letter.py` | Analytics summary, audit log, and Postgres DLQ table (`dead_letter_events`). |
| `services/analytics_service.py` | Dashboard queries — summary from Postgres, breakdowns (browser/OS/device/geo/UTM/referrers) from Mongo aggregation. `days` (1–90) scopes the device/UTM/referrer breakdowns; device breakdown fetches total/unique/devices via `asyncio.gather`. |
| `services/audit_service.py` | Audit logging. |
| `services/billing_service.py` | Plan upgrade/downgrade — validates the target plan against `PlanEnum`, persists via `UserRepository`, invalidates the rate-limit plan cache. |
| `routes/analytics.py`, `routes/audit_logs.py`, `routes/billing.py` | HTTP endpoints (note: `billing.py` is **plan upgrade only** — no payments/Stripe; handlers call `BillingService`). |
| `workers/analytics_worker.py` | Consumes `url-clicked` → parses user-agent → writes Mongo `ClickEvent` + upserts Postgres summary counters (Story 8). |
| `workers/aggregation_worker.py` | Periodic 60s loop — aggregates Mongo click events → `URLAnalyticsSummary` in Postgres (the cross-DB write from Story 15). **Single writer** for click counters (Story 22); watermark = `max(clicked_at)` of the window persisted *after* DB writes so a crash re-runs the window instead of dropping it; uses shared shutdown helpers (Story 24). |
| `repositories/analytics_repository.py`, `audit_log_repository.py` | DB queries for summaries/audit logs. |

### `admin/`
| File | What it does |
|---|---|
| `services/admin_service.py` | Cross-aggregate admin queries (users/workspaces/URLs counts + listings, superadmin seed/toggle) — depends only on repositories, no session. |
| `routes/admin.py` | Admin endpoints: seed superadmin, user management (list/toggle-superadmin/delete), workspace + URL listing, platform stats (handlers call `AdminService`). |

## Frontend — `frontend/src/`

### Core plumbing
| File | What it does |
|---|---|
| `proxy.ts` | Next.js proxy (replaced middleware.ts, Next 16 convention) — validates tokens, manages cookies on the server side. |
| `lib/api.ts` | API client — fetch wrapper, `auth.refresh` via HttpOnly cookie, `auth.exchangeOauth` (Story 20), `csvEscape` for bulk CSV, error handling. |
| `lib/auth-prefetcher.tsx` | Prefetches the `me` auth query into the React Query cache on mount (renders null); used in the authenticated layout. |
| `lib/providers.tsx` | React Query provider wrapper. |
| `lib/schemas.ts` | Zod validation schemas shared by forms. |
| `lib/utils.ts` | `cn()` helper (clsx + tailwind-merge). |
| `store/auth.ts` | Zustand auth store (user, isLoading, setUser, logout). |
| `queries/index.ts` | TanStack Query hooks for a subset of resources — auth, urls, workspaces, folders, tags, api-keys, favorites, webhooks, audit-logs (18 hooks). |
| `hooks/useDashboard.ts` | Dashboard data aggregation hook. "Active" stat uses a separate `status=active&limit=1` query's `total` (the 50-item list undercounts); API-key quota aggregated across the user's active keys against the plan limit. |
| `components/layout/sidebar.tsx` | App navigation sidebar. |
| `components/ui/*` | Reusable UI kit (button, card, dialog, dropdown, input, select, table, tabs, etc.). |

### Pages
| File | What it does |
|---|---|
| `app/layout.tsx` | Root layout + providers. |
| `app/page.tsx` | Public landing page (marketing). |
| `app/login/page.tsx`, `register`, `forgot-password`, `reset-password`, `verify-email` | Auth pages (Story 12 for the cookie/OAuth flow). |
| `app/(authenticated)/layout.tsx` | Protected app shell — `<Sidebar>` + `<AuthPrefetcher>` (the auth guard is per-page via `auth.me()`). |
| `app/(authenticated)/dashboard/page.tsx` | Overview analytics. |
| `app/(authenticated)/urls/page.tsx` | URL list + search/filters. |
| `app/(authenticated)/urls/new/page.tsx` | Create URL form. |
| `app/(authenticated)/urls/[id]/page.tsx` | URL detail. |
| `app/(authenticated)/urls/[id]/analytics/page.tsx` | Per-URL click analytics charts. |
| `app/(authenticated)/favorites`, `folders`, `tags`, `bulk`, `workspaces`, `webhooks`, `webhooks/receiver`, `api-keys`, `billing`, `audit-logs`, `admin`, `profile` | The rest of the feature pages. |
| Each folder's `loading.tsx` / `error.tsx` | Next.js loading and error UI states (note: `profile` and `login` have `loading.tsx` but no `error.tsx`). |

### Tests
| File | What it does |
|---|---|
| `test/*.test.ts(x)` | Vitest unit/component tests (153 total). |
| `test/mocks/handlers.ts`, `test/mocks/server.ts` | MSW (Mock Service Worker) fake API for tests. |
| `test/setup.ts`, `test/test-utils.tsx` | Test bootstrap + render helpers. |

## Repo-level files
| File | What it does |
|---|---|
| `backend/src/` | All Python backend code. |
| `frontend/src/` | All React/TypeScript frontend code. |
| `backend/alembic/`, `alembic.ini` | Database migrations (run at boot, Story 5) — including `f5e6d7c8b9a0` hot-path indexes (Story 25). |
| `backend/tests/` | Backend test suite (unit + integration/testcontainers). |
| `backend/render.yaml` | Render deployment config for the **backend only** (Story 14). |
| `backend/Dockerfile`, `entrypoint.sh` | Image build + migration-at-boot entrypoint. |
| `docker/docker-compose.yml` | Local full-stack (Postgres, Mongo, Redis, Kafka, backend, frontend). |
| `.github/workflows/ci.yml` | CI pipeline (Story 13). |
| `AGENTS.md` | Operational rules + critical-fix documentation (our "institutional memory"). |
| `docs/INTERVIEW_GUIDE.md` | This file. |

**Study tip:** the highest-value files to actually read are `main.py`, `config.py`, `database.py`, `workspace_repository.py`, `url_service.py`, `redirect_service.py`, `analytics_worker.py`, `kafka.py`, and `proxy.ts`. If you can explain those from memory, you can explain the whole project.

---

*Generated from the real development history of this repository. Re-read Part 4 out loud before interviews — the STAR structure is what interviewers remember. Use Part 7 to actually learn what each file does so you can discuss the code honestly.*
