# Critical Fixes

## Auth — Logout Reload Loop + OAuth Sign-In Failing/Slow

**Symptom:** Logout made the dashboard reload forever; Google sign-in could hang/fail silently after "continue" and felt slow (forced Google consent screen every time).

**Root causes:**
- `frontend/src/components/layout/sidebar.tsx` fired `auth.logout()` and navigated to `/login` immediately — the server's `Set-Cookie` (delete) never landed, the httpOnly `access_token` cookie survived, and `frontend/src/proxy.ts` bounced `/login` → `/dashboard` forever.
- `backend/src/identity/routes/auth.py` `logout` depended on `bearer_scheme` (`HTTPBearer(auto_error=True)`) — a 401 aborted the handler **before** the `delete_cookie` calls ran, so a stale/invalid token blocked cookie clearing.
- `frontend/src/lib/api.ts` `auth.logout` used `apiFetch` → on 401 it triggered `handleUnauthorized()` (refresh → `/login?redirect=`), which fought the proxy bounce and looped.
- `proxy.ts` bounced `/login` → `/dashboard` even when the URL carried the one-time OAuth handoff `code` — a stale-but-valid cookie swallowed the handoff and the user never got signed in.
- OAuth exchange only returned a refresh token to the client; the login page then had to call `auth.refresh(refresh_token)` — one extra round trip where a failure after the one-time code was consumed stranded the login.
- `google_oauth.py` used `prompt=consent`, forcing the Google consent screen on **every** sign-in (extra click + load).

**Fixes:**
- `logout` now uses `bearer_scheme_optional` (`HTTPBearer(auto_error=False)` added in `deps.py`), blacklists best-effort, and **always** deletes both auth cookies.
- `auth.logout` in `api.ts` is a raw `fetch` (no `apiFetch` 401-refresh machinery); `sidebar.handleLogout` **awaits** it before `window.location.href = "/login"`.
- `proxy.ts`: auth pages are only bounced to `/dashboard` when they carry no `code` (OAuth handoff) and no `expired=1` param; `handleUnauthorized` now redirects to `/login?expired=1` so a stale cookie can't cause a bounce loop.
- `oauth_exchange` (`auth.py`) now mints the access token, sets **both** auth cookies server-side (like `login`), and returns a full `Token`. The login page chain is now `exchangeOauth(code) → auth.me() → redirect` — no intermediate refresh hop.
- `google_oauth.py`: `prompt=consent select_account` (forces the account chooser **and** consent confirmation on every sign-in).

**Note:** forcing re-consent every login was a deliberate user decision (Google asks each time). GitHub has no `consent` prompt — `github_oauth.py` sends `prompt=select_account`, which forces the account picker every time (GitHub auto-completes repeat authorizations with unchanged scopes, so the authorize page itself only re-appears when scopes change).

**Note:** cookies are httpOnly, so JS `clearTokens()`/`document.cookie` cannot delete them — cookie clearing must happen server-side (logout response or the proxy's max-age-0 delete for expired tokens).

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

## OAuth — Refresh Token Rode the Callback URL (leaked in logs/referrer)

**File:** `backend/src/identity/routes/auth.py`, `backend/src/identity/services/auth_service.py`, `frontend/src/lib/api.ts`, `frontend/src/app/login/page.tsx`

The Google/Refresh OAuth callback passed the provider refresh token as a `?code=` query param; it ended up in browser history, server logs, and the Referer header of any subsequent navigation.

**Fix:** the callback now writes a **one-time handoff code** to Redis (TTL 120s) and redirects to `/login?code=<handoff>`; the frontend calls `POST /auth/oauth/exchange` with that code, which swaps it for a session in a server-side POST body. `create_oauth_handoff` / `exchange_oauth_handoff` in `auth_service.py`.

## API-Key Quota — Enforcement Was Dead Code

**File:** `backend/src/shared/core/deps.py`, `backend/src/shared/core/api_key_auth.py`

`verify_api_key_quota` was defined but never called from `get_current_user`'s API-key branch → quota (per-user daily limit) was never enforced.

**Fix:** `get_current_user` calls `verify_api_key_quota(api_key_id, user_plan)` on every API-key request. It uses an atomic Redis `CHECK_AND_INCREMENT_LUA` script (increment + compare to `daily_limit`) with an in-process `dict` fallback when Redis is unavailable. No blocking counter → burst limits still enforced, no token bucket needed per request.

## One-Time Links — TOCTOU on Consume

**File:** `backend/src/links/repositories/url_repository.py` function `consume_one_time`, `backend/src/links/services/redirect_service.py`

`consume_one_time` did a read-then-write (SELECT active → UPDATE active=0) → two concurrent hits could both pass the check and both redirect.

**Fix:** consume is now a single conditional UPDATE (`UPDATE urls SET active=0 WHERE id=:id AND active=true`); a rowcount of 0 → `URLNotFound`. One winner only.

## Geo Lookup — Removed From Redirect Hot Path

**File:** `backend/src/links/services/redirect_service.py`, `backend/src/analytics/workers/analytics_worker.py`, `backend/src/shared/core/geo_service.py`

The redirect handler resolved the visitor's IP synchronously via geoip2 per click → DNS/IP stack latency on every redirect. Separately, `GeoService._is_public_ip()` was missing so internal/private IPs would be geo-resolved and their topology recorded.

**Fix:** geo is resolved **asynchronously** in `analytics_worker.process_event` (same `GeoService().resolve(ip)`), off the redirect path. `_is_public_ip()` now rejects private/loopback/link-local/multicast/reserved/unspecified and unwraps IPv4-mapped IPv6 before geolocating.

## Aggregation Worker — Watermark Could Re-Process or Drop a Window

**File:** `backend/src/analytics/workers/aggregation_worker.py`

The cutoff was derived from `now - 60s` rather than the events actually aggregated, and was persisted before DB writes → crash windows could be silently dropped or double-aggregated.

**Fix:** after the aggregation queries complete and the DB writes succeed, persist `last_cutoff = max(clicked_at)` of the actually-aggregated events. Empty windows save `now - 1s`. Crash re-runs the window instead of dropping it.

## Kafka Producer — `close_kafka` Could Drop In-Flight Sends

**File:** `backend/src/shared/events/kafka.py`

`producer.stop()` was called immediately, aborting messages still in the producer's flush queue → events lost on shutdown.

**Fix:** `publish_raw`/`publish` track in-flight coroutines in `_pending_sends`; `close_kafka()` awaits them (10s cap) before stopping the producer.

## Polling Workers — Non-Graceful SIGTERM/SIGINT

**File:** `backend/src/links/workers/cleanup_worker.py`, `backend/src/links/workers/expiry_worker.py`, `backend/src/webhooks/workers/webhook_retry_worker.py`, `backend/src/shared/workers/kafka_consumer_pool.py`

`KeyboardInterrupt`/`CancelledError` escaped the asyncio loops → dirty exit, partial batches, noisy logs.

**Fix:** all polling workers use the shared `shared.workers.shutdown` helpers (`install_signal_handlers()` + `wait_for_shutdown()` with `asyncio.wait_for(asyncio.shield(...))`); `kafka_consumer_pool` re-raises `CancelledError`, shields `consumer.stop()` in `finally`, and re-raises on backoff-sleep cancellation.

## Hot-Path Indexes — Missing FK/Status/Expiry Indexes

**File:** `backend/alembic/versions/f5e6d7c8b9a0_add_hotpath_indexes.py`

`api_keys.prefix`, `urls.workspace_id`, `urls.expires_at`, `webhook_events.status` lacked indexes → API-key auth, workspace listing, expiry scans, and webhook retry queries did full scans.

**Fix:** new migration `f5e6d7c8b9a0` (parent `f490c0f533a4`) creates `ix_api_keys_prefix`, `ix_urls_workspace_id`, `ix_urls_expires_at`, `ix_webhook_events_status`; models use `index=True`.

## Analytics Breakdown — `days` Not Scoped (Unbounded Aggregates)

**File:** `backend/src/analytics/services/analytics_service.py`, `backend/src/analytics/routes/analytics.py`

Devices/UTM/referrer breakdowns aggregated all history regardless of the requested range, and ran sequentially.

**Fix:** `days` (1–90) now scopes all three breakdowns; device breakdown fetches total/unique/devices via `asyncio.gather`; responses include `days`. Frontend breakdown APIs pass `days` through.

## Frontend — Query Error States, Dashboard Counts, URL Form Defaults

**Files:** `frontend/src/app/(authenticated)/**/page.tsx`, `frontend/src/hooks/useDashboard.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/schemas.ts`

- All list/detail pages (favorites, folders, tags, audit-logs, webhooks, webhooks/receiver, `urls/[id]`, `urls/[id]/analytics`, bulk, workspaces, api-keys) now surface query `isError` with a "Try again" refetch instead of silently rendering empty states. `urls/[id]/analytics` shows an inline breakdown banner with `refetchBreakdowns`.
- Dashboard "Active" stat uses a separate `status=active&limit=1` query's `total` (the 50-item list undercounted beyond page 1).
- Dashboard API-key quota aggregates `sum(daily_limit - remaining_quota)` across the user's active keys against the plan limit (enforcement is per-user).
- `urls/new` defaults the workspace to the first workspace and validates `workspace_id >= 1` (was submitting `0`).
- `expires_at` is edited in local wall-clock (`datetime-local`) instead of UTC `toISOString().slice(0, 16)`.
- api-keys revoke: `window.confirm` + pending state + toast + query cache invalidation instead of `window.location.reload()`.
- Bulk CSV cells escaped (`csvEscape`: quote + double embedded quotes); broken `bulkApi.update` removed; `apiKeysApi.quota` typed as `{ api_key_id, remaining_quota, daily_limit, resets_at }`.
- Test-only: `api-keys-page.test.tsx` and `hooks.test.ts` wrap renders in a `QueryClientProvider` (components now call `useQueryClient`/`useQuery`).

## Deleted URLs Kept Redirecting + Misc Audit Fixes

**Files:** `backend/src/links/services/redirect_service.py`, `backend/schemas/avro/url-clicked.avsc`, `backend/src/admin/routes/admin.py`, `backend/src/webhooks/workers/webhook_click_consumer.py`, `backend/src/shared/core/geo_service.py`, `backend/src/shared/events/kafka.py`, `backend/src/webhooks/workers/dlq_replay_worker.py`, `backend/src/shared/workers/shutdown.py`, `backend/src/main.py`, `backend/src/shared/core/safe_url.py`, `backend/src/webhooks/services/webhook_service.py`, `backend/src/webhooks/workers/metadata_worker.py`, `frontend/src/app/login/page.tsx`, `frontend/src/proxy.ts`, `frontend/src/app/(authenticated)/favorites/page.tsx`, `frontend/src/queries/index.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/schemas.ts`

- **Soft-deleted URLs redirected forever:** `redirect_service._validate` only rejected `active=false`/`expired` — a `status="deleted"` row kept 302-ing until the cleanup worker hard-deleted it. `_validate` now raises `URLNotFound()` for `status == "deleted"`. All delete paths already purge the redirect cache.
- **UTM analytics empty in prod:** `url-clicked.avsc` was missing `utm_source`/`utm_medium`/`utm_campaign`; `fastavro.schemaless_writer` silently drops unknown keys, so the worker wrote no UTM data. Added the three nullable fields to the Avro schema.
- **Admin password-hash leak:** `GET /admin/users`, `GET /admin/workspaces`, `GET /admin/urls` returned raw ORM rows (including `password_hash`/`google_id`); `GET /admin/users/{user_id}` had no `response_model`. All now return safe response models (`AdminUserList`/`AdminWorkspaceList`/`AdminURLList`, `UserResponse`).
- **Webhook delivery semantics + loss window:** `deliver_click_webhooks` counted every non-exception status as `delivered` (5xx/429 silently "succeeded") and set the Redis idempotency key *before* `db.commit()` (crash in between permanently lost the event). Now only 2xx = delivered (5xx/429 → `failed`, handled by the retry worker), Redis get/setex guarded (best-effort), idempotency key set only after commit.
- **Unguarded Redis on redirect hot path:** `geo_service` cache `get`/`setex` could raise and fail the redirect. Both are now try/except (cache miss → re-resolve).
- **DLQ temp-producer leak:** `kafka._send_and_stop` only stopped the producer on success; a failed `send_and_wait` leaked it. Stop is now in `finally`.
- **DLQ replay worker dies on startup outage:** `init_kafka()` (5 retries then raises) killed the worker permanently while `safe_consume` retries forever. It now loops/backs off until Kafka is reachable.
- **Embedded workers clobbered uvicorn signals:** `install_signal_handlers` used `loop.add_signal_handler`, which **replaces** uvicorn's handler → SIGTERM hung the process. `main.py` sets `EMBEDDED_WORKERS=1` before starting embedded workers; `install_signal_handlers` now returns early when that env is set.
- **Webhook SSRF:** webhook create/update/delivery URLs were unvalidated → arbitrary POSTs to internal hosts/metadata endpoints. Moved the metadata worker's `_resolve_public`/`_is_safe_url` helpers into `src/shared/core/safe_url.py` (`is_safe_url`); `webhook_service.create`/`update` reject URLs that don't resolve only to public IPs. Metadata worker imports the shared module.
- **CI webhook route tests (400 → NXDOMAIN):** `tests/test_routes/test_webhook_routes.py` created webhooks against `https://hooks.example.com/callback`, but `hooks.example.com` has no DNS records on GitHub runners → `is_safe_url` correctly rejected it → 400 → `Backend Tests` CI was red (`7 failed, 316 passed`). Tests now use `https://example.com/callback` (public, resolves on runners — same host the metadata-worker test already fetched for real), and a `test_create_webhook_private_url_rejected` asserts `http://127.0.0.1/callback` → 400 (numeric literal, no DNS needed).
- **Login ignored `?redirect`:** `redirectAfterLogin` always went to `/dashboard`; deep links bounced through login landed wrong. It now honors a validated `redirect` param (single leading `/`, rejects `//`) while keeping invite-token priority.
- **Proxy dropped redirect query string:** `redirect` param saved only `pathname`, so `/workspaces?invite_token=…` lost the token. Now `pathname + request.nextUrl.search`.
- **Favorites key collision + 20-cap:** the favorites page used the same `["favorites"]` query key as `useFavorites` even though the two queries resolve to different shapes (`URLItem[]` vs `Favorite[]`), so the last-mounted page's data won. Page now uses `["favorites-with-urls"]`; both call `list(0, 100)` so star-state and the page resolve beyond the backend's default 20-item limit.
- **`rawFetch` 401-retry crash on 204:** retry path called `retry.json()` on `204 No Content` (JSON.parse("") throws) for void endpoints like audit-log export. Now returns `undefined` on 204.
- **`custom_alias` zod min mismatch:** frontend schema had no min length; backend enforces `min_length=3`. Added `.min(3)`.

## OAuth — Static `/oauth/exchange` Shadowed by `/oauth/{provider}` (sign-in always failed)

**File:** `backend/src/identity/routes/auth.py`

`POST /auth/oauth/{provider}` (initiate) was declared **before** `POST /auth/oauth/exchange`. Starlette matches routes in registration order, so every handoff exchange hit `initiate_oauth("exchange")` → 400 `"OAuth provider 'exchange' is not configured"` → the login page's `exchangeOauth()` catch showed "OAuth login failed. Please try again." Google **and** GitHub were both broken — the symptom is identical regardless of provider because both converge on the same broken exchange route.

**Fix:** declare `oauth_exchange` **before** `initiate_oauth` so the static path wins (Starlette/Route precedence is order-based, not specificity-based). Regression test added in `tests/test_routes/test_auth_routes.py` (`test_oauth_exchange_not_shadowed_by_provider_route`: an unknown code must 401 `InvalidToken`, not 400 "not configured").

**Note:** this is the second time route ordering mattered here — keep new static paths under `/oauth/...` above the parameterized ones.

## OAuth — "Internal Error" Was Stale asyncpg Pooled Connections

**File:** `backend/src/shared/core/database.py`

OAuth callbacks 500'd with `asyncpg.exceptions._base.InterfaceError: connection is closed` on the `users` SELECT **after** the Google/GitHub token exchange already succeeded. Root cause: the production engine created a `pool_size=20` asyncpg pool with no `pool_pre_ping`/`pool_recycle`. Neon's free tier sleeps the compute after ~5 min idle and drops server-side connections; the pool then checked out a dead asyncpg connection on the next request → `connection is closed` → 500 ("Internal Error"). This hit **all** auth paths (`get_by_email` in password login, OAuth callback), not just OAuth — the symptom was worst on OAuth because the sign-in flow pauses at the provider's consent screen while the DB sleeps.

**Fix:** `create_async_engine(..., pool_pre_ping=True, pool_recycle=300)`. On checkout SQLAlchemy pings the connection (`SELECT 1`); a dead one is invalidated and replaced instead of being handed to the request. `pool_recycle=300` recycles connections before the pooler's idle-timeout kills them. Test engines use `NullPool` so they're unaffected.

## Auth — Refresh-Token Reuse Detection + OAuth PKCE

**Files:** `backend/src/shared/core/security.py`, `backend/src/identity/services/auth_service.py`, `backend/src/identity/services/sso/google_oauth.py`, `backend/src/identity/services/sso/github_oauth.py`, `frontend/src/lib/api.ts`

Every refresh token now carries a `jti` (`secrets.token_urlsafe(32)`) and a per-session `sid`. `create_refresh_token(data, sid=None)` auto-generates `sid` when omitted.

**Reuse detection model:** one Redis record per session, `refresh:session:{sid}` = JSON `{jti, prev_jti, prev_at, created}` (TTL 7d). A refresh runs atomic Lua `_ROTATE_REFRESH_LUA` via `RedisAdapter.eval`:
- returns `1` — presented `jti` is the current one (or the grace `prev_jti` within 30s) → rotate, keep `prev_jti`/`prev_at`, mint new tokens with the **same `sid`**;
- returns `0` — presented `jti` is a replayed old token → `_revoke_refresh_family(user_id)` sets `refresh:revoked:{user_id}` (TTL 7d) and raises `TokenRevoked` (whole session dies);
- returns `-1` — no session record for the `sid` → reject with `TokenRevoked` **without** family revocation (legit logout cleanup, or an attacker's fresh token).

Legacy pre-session tokens (no `sid`/`jti`) still rotate and are upgraded to session metadata on first refresh, so detection progressively covers all users. `login()`/`oauth_callback()` call `_store_refresh_session()` (best-effort, try/except); `logout()` deletes `refresh:session:{sid}`. The frontend's `tryRefresh()` is single-flight (one shared `refreshPromise`, reset in `.finally`) so concurrent 401s fire one refresh and don't trip the 30s reuse grace.

**PKCE (S256):** `oauth_init()` stores a `code_verifier` at `oauth:pkce:{state}` (TTL 600s, single-use — deleted on callback) and sends `code_challenge`/`code_challenge_method=S256` in the authorize URL; `oauth_callback()` fetches the verifier and passes it to `authenticate(code, code_verifier=...)`. Provider `get_authorization_url(state, code_challenge=None)` / `exchange_code(code, code_verifier=None)` are optional-kwarg based — the auth-service handoff path supplies them.

**Google consent every login:** `google_oauth.py` sends `prompt=consent select_account` (account chooser + consent confirmation each time — deliberate user decision); `github_oauth.py` sends `prompt=select_account` (GitHub cannot force re-consent for unchanged scopes; account picker is the max).

## Render Deploy — "Port scan timeout reached" / "Timed Out"

**File:** `backend/start.sh`, `backend/render.yaml`

Render's free tier spins the DB down with inactivity; the old start command ran `alembic upgrade head && uvicorn` synchronously, so a cold DB wake delayed uvicorn's port bind past Render's port-scan window → deploy "Timed Out" even though the build succeeded. `start.sh` runs migrations in the background (`uv run alembic -c alembic.ini upgrade head &`) then `exec uv run uvicorn ... --port "${PORT:-8000}"`, so the port binds immediately and migrations finish alongside startup. `render.yaml` `startCommand` → `sh start.sh`. `SKIP_MIGRATIONS=1` still disables the migration step.

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

## ⚠️ Tests send REAL emails if SMTP is configured in `.env`

`backend/.env` has real Gmail SMTP credentials. `EmailService._send` sends real email whenever `is_configured()` is true — and the workspace-invite email was **not mocked** in the test fixture, so `pytest --use-testcontainers` fired real invites to `invited@example.com` (which bounced) into the real inbox.

**Fix:** the autouse `mock_external_services` fixture in `tests/conftest.py` now:
1. Patches `EmailService.is_configured` → `False` for **every** test (root-cause guard — `_send` short-circuits before SMTP for any current or future callsite).
2. Also mocks `workspace_service.EmailService.send_invite_email` (alongside the existing auth email mocks).

**Rule:** never add an email callsite without adding it to this fixture's patch list — the `is_configured` guard is the safety net, the per-callsite mock is the explicit intent.

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
