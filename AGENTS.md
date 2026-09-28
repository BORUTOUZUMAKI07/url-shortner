# Critical Fixes

## Audit Batch 3 — Idempotency, Cache Eviction, Rotation Ordering, Verification Lockout

Four lowered-value audit items plus readiness work for the `REQUIRE_EMAIL_VERIFICATION` flag. The recurring theme this batch: **a control implemented as two dependent steps** (check-then-set, evict-in-a-loop, revoke-then-create, pre-check-then-INSERT) whose failure mode is a silent duplicate, a silent latency tax, a silent lockout, or a 500 where a 409 belongs.

### Webhooks — click dispatch idempotency was check-then-set (two consumers, two deliveries)

**Files:** `backend/src/webhooks/workers/webhook_click_consumer.py`, `backend/src/shared/core/redis.py` (`setnx`)

`deliver_click_webhooks` did `get()` → deliver → `setex()`. Between the read and the write, a concurrent consumer — or a Kafka redelivery before the offset commit lands, with `auto_offset_reset=earliest` — also read "absent", and **both batches POSTed the same event to the endpoint**.

Replaced with a two-state marker on **one** key, both via new `RedisAdapter.setnx` (atomic: the get and the set are one decision, exactly one caller wins):

1. **claim:** `setnx(key, PROCESS_LOCK_SECONDS=90, "1")` before any DB work — a short lock held while delivering; a second consumer sees the key and skips.
2. **success:** after `commit`, `setex(key, DONE_TTL_SECONDS=7d, "1")` extends the same key into the long completion marker, so replays within a week are suppressed.
3. **failure:** `delete(key)` releases the claim so a redelivery retries; the lock TTL is the backstop for a hard kill that skips the line.

Two keys, or claim-forever, would each lose one guarantee: `process`-only would let a redelivery re-deliver minutes later; a long TTL set at claim time stays set through a crash mid-delivery and permanently skips the event.

Tests: `tests/test_core/test_webhook_click_idempotency.py` pins the interleaving (`setnx` before `db_enter`, `setex` after `db_commit`, no `get`, delete on failure, no idempotency key for events without an id); `tests/test_core/test_redis_setnx.py` covers the adapter on both the Upstash and plain-Redis branches, and the new `delete_url_caches` batch.

### Bulk ops — cache eviction was N round trips; QR generation loaded every row to keep three

**Files:** `backend/src/links/services/bulk_service.py`, `backend/src/links/repositories/url_repository.py` (`get_urls_by_ids`), `backend/src/shared/core/redis.py` (`delete_url_caches`)

The four bulk mutators (update / disable / reactivate / delete) evicted the redirect cache with a per-URL `delete_url_cache` loop — one Upstash HTTPS request (~100-200ms) per URL, **serial**. A 50-URL bulk delete paid ~10s of pure round-trip latency on top of the DB work. `delete_url_caches(short_codes)` is now one `delete_many` round trip. It is best-effort (`try/except`: a stale cache entry is refreshed by the next hit, but a redirect that fails because Redis threw is worse) and an empty batch is a no-op.

`generate_qr_zip` loaded *every* URL in the workspace and filtered in Python — an N-row SELECT to keep 3 rows, where N is whatever the workspace happens to have. New `URLRepository.get_urls_by_ids(url_ids, workspace_id)` filters in SQL (scoped to the workspace, `status != deleted`, unexpired, tags loaded).

Tests: `test_redis_setnx.py` (`test_delete_url_caches_evicts_batch_in_one_round_trip`, empty no-op, Redis-failure tolerance).

### API keys — rotation revoked the old key before the replacement existed

**File:** `backend/src/identity/services/api_key_service.py`

`rotate` revoked the old key, *then* generated and hashed the new one. Any failure in that second half — a DB blip on `create`, a crash between the two statements — left the user with **zero working keys** until they generated one manually. The Argon2 hash is CPU-bound (~100-300ms) and was computed inside the `create` call, *after* the revoke.

Order is now: generate raw → hash (before any DB write, so a rotation can never destroy the old key and then fail to build the replacement) → `create` new row → `revoke` old. The only remaining window is both-valid for a moment if `revoke` fails after `create` — which locks nobody out. Tests: `tests/test_core/test_api_key_rotation.py` pins `["get", "create", "revoke"]` and asserts the old key survives a failed create (`"revoke" not in calls`).

### Signup — the unique-email race was a 500; the OAuth loser failed the user

**File:** `backend/src/identity/services/auth_service.py`

`register` pre-checks `email_exists` and then INSERTs. Two requests with the same address can both pass the check before either INSERT commits; the unique constraint lets one win and the loser's `IntegrityError` escaped as a **500** — for a condition the pre-check only exists to detect. The loser now rolls back (the transaction is invalid from the failed INSERT on) and raises `EmailAlreadyExists` → 409. Tests: `tests/test_core/test_register_integrity_race.py` (repo stub whose `create` raises; asserts `EmailAlreadyExists` and that `rollback` ran).

Same race in `oauth_callback`: two first-time sign-ins with the same provider subject both pass the `get_by_oauth_sub` lookup and both CREATE. The loser now rolls back, re-fetches the **winner** (by provider subject, never by email), and skips `create_default` via a new `created_here` flag — the winner already created the default workspace on their own INSERT. If the winner vanished (both rolled back), it fails cleanly with `OAuthFailed` instead of a 500. Tests: `tests/test_core/test_oauth_callback_race.py` (drives `_run_oauth_callback` with stub repos; asserts adopt-by-subject, no duplicate default workspace, and a returned session).

### Verification lockout — refresh bypassed the gate, and lockout had no recovery

**Files:** `backend/src/identity/services/auth_service.py`, `backend/src/identity/routes/auth.py`, `backend/src/identity/schemas/user.py`, `frontend/src/app/login/page.tsx`, `frontend/src/lib/api.ts`

`login` already enforced `REQUIRE_EMAIL_VERIFICATION`; `refresh` did **not** — anyone who logged in before the flag was enabled kept minting fresh access tokens via refresh, so the policy would have been a lie for every pre-existing session. `refresh` now raises the same `UnauthorizedError("Email address is not verified")` → 401 (which is what sends the frontend to the login page's resend path).

The gate makes an unverified user a **stranger** to the only system that could help them: the login refusal also bars `/auth/resend-verification`. And the signup mail's token expires after 24h — so a user locked out days later had no path back at all. New unauthenticated `POST /auth/verify-email/resend` (`resend_verification_for_email`), modeled on `forgot_password`:

- unknown address → generic 200, no mail, audit row (anti-enumeration);
- verified address → generic 200, no mail;
- unverified + SMTP unconfigured → **503** (a server fault retrying cannot fix; the detail tells the user to contact an administrator);
- unverified + SMTP configured → one mail with a fresh 24h token.

Rate-limited 5/5 min, keyed on the shared client IP. The login page renders an inline resend card when the failure message contains "not verified", with sent / 503 feedback. Tests: `tests/test_core/test_email_verification_resend.py` (service outcomes + the refresh gate trio: unverified×flag-on raises, verified×flag-on works, unverified×flag-off works), `tests/test_routes/test_auth_routes.py` (503 when SMTP off, generic 200 for unknown, sends-once when configured).

**Note (stale-note correction):** an earlier section claimed the profile page's "Email not verified" card had **no resend endpoint** — that was wrong. `POST /auth/resend-verification` (authenticated) and the profile page's "Resend" button were already wired and still are; what was genuinely missing was the **unauthenticated** recovery for locked-out users, which this batch adds. The original warning still stands and now matters twice: SMTP misconfiguration hides as "Would send email to…" log lines — configure SMTP *before* flipping `REQUIRE_EMAIL_VERIFICATION`, and when mail is unavailable both resend endpoints now report 503 instead of silently promising a mail.

## Audit Batch 2 — Revocation That Un-Fired, Silent PKCE Loss, Cross-Tenant Cancel

Three background audits, every finding verified against source before fixing. The
recurring theme is **a control that degrades to absent rather than failing**, so
nothing logs and nothing breaks visibly.

### Auth — a logged-out token became valid again after 60 seconds

**File:** `backend/src/shared/core/deps.py`

`get_current_user` cached the JWT blacklist in a module-level dict to avoid an
Upstash round trip per request. The logic was:

```python
if cached is not None and cached > now: raise TokenRevoked()
if cached is None:  <consult Redis>       # <-- the bug
```

The second arm is guarded on `cached is None`, but an entry that has **aged out**
of the dict is a float in the past — *not* `None`. So: logout blacklists the
token in Redis and caches it for 60s → requests for 60s are correctly refused →
request 61 finds a stale float, **neither arm fires**, and the token is decoded
and accepted. A revoked token was replayable for the rest of its life.

An aged-out entry is now treated as the cache miss it is, which is what the
comment above the cache has always claimed. This also removes an unbounded leak:
the dict was written once per revoked token and never pruned.

**Note:** this is the *same class* of mistake as the GitHub OAuth bug above —
`cached is not None` read as "we have a decision" when it means "we have a
number". Whenever a cache stores a value with a TTL, the expiry branch must fall
through to the authoritative source, not past it.

Tests: `tests/test_core/test_blacklist_cache.py` (7). 4 fail on the unfixed code
with `DID NOT RAISE TokenRevoked`; 3 are baseline guards that must pass either way.

### OAuth — a failed state write silently disabled PKCE for that sign-in

**File:** `backend/src/identity/services/auth_service.py`

`oauth_init` wrote the state and the PKCE verifier as two serial `SETEX` calls. A
transient Redis error between them left `oauth:state:{state}` stored with **no**
`oauth:pkce:{state}`. The callback resolves a missing verifier to `None` and
calls `authenticate(code, code_verifier=None)` — a token exchange with **no PKCE
at all**, after having advertised a `code_challenge` to the provider.

Nothing surfaces this. The code is single-use and short-lived, so it presents as
one sign-in that is marginally more forgeable and nothing else. Now written
together by `_INIT_OAUTH_STATE_LUA` — one round trip, both keys or neither.

**Note:** same shape as the handoff double-redemption in `f8a1740`. A control
that degrades to absent leaves no log line, so it cannot be found by looking.

### Workspaces — `cancel_invite` had no ownership check

**File:** `backend/src/workspaces/services/workspace_service.py`

`cancel_invite(invite_id, workspace_id)` read the invite and updated it, trusting
the caller's `workspace_id` without comparing it. Any member who learned an invite
id could cancel an invite in a workspace they have no role in. `remove_member`
and `update_member_role` both verified; this one did not.

### Workspaces — `accept_invite` was a read-then-write race

**Files:** `workspace_service.py`, `repositories/workspace_invite_repository.py`

Two concurrent accepts could both pass the `status == "pending"` check and both
create a membership. `invite_repo.accept()`'s `None` "already accepted" signal was
discarded by the caller anyway.

Replaced with `claim_pending(invite_id) -> bool` — a single conditional
`UPDATE ... WHERE id=:id AND status='pending'`, rowcount as the signal. The claim
runs **first**, then the membership insert, and that one commit persists both, so
a rollback undoes the claim and the invite stays redeemable. `IntegrityError` now
becomes `AlreadyMember` (409) instead of a 500. The dead `accept()` is removed.

### Links — uniqueness that was only enforced in Python

**Files:** `favorite_service.py`, `folder_service.py`, `models/folder.py`, migration `d4e5f6a7b8c9`

- Folders had **no** uniqueness constraint at all — every other "unique name"
  (workspace, tag, API-key) had one. Two same-named folders render side by side
  and the user cannot tell them apart. New `uq_folder_name_workspace`. The
  migration dedupes first, **reassigning `urls.folder_id`** to the survivor: the
  FK is `ON DELETE SET NULL`, so dropping a duplicate would silently orphan its URLs.
- `favorite_service.add` and `folder_service.create` let a unique-violation
  `IntegrityError` escape as a 500 → now `ConflictError` (409).

### Analytics — totals were all-time, the chart beside them was period-scoped

**Files:** `analytics_service.py`, `routes/analytics.py`

`GET /analytics/summary` accepted a `days` parameter **the route never declared**.
FastAPI discards query params a path operation does not declare, so the value was
silently dropped: headline numbers were lifetime totals while the daily chart next
to them honoured the selected range. "Last 7 days: 1,204" above bars summing to 90.

`days` is now declared and applied via a single Mongo `$facet`, so totals and
series still cost one round trip.

### Analytics — the rollup watermark moved from Redis to Postgres

**Files:** `aggregation_worker.py`, `analytics_repository.py`, `models/analytics.py`, migration `e5f6a7b8c9d0`

`upsert_rollup` committed internally, then the worker persisted the watermark to
Redis as a **separate write**. A crash between them re-aggregated an
already-counted window; the reverse ordering would have dropped one. The
watermark is now a row in `aggregation_watermarks`, written in the same
transaction as the rollup. Redis is kept as a non-load-bearing cache, and the
migration seeds from it so a deploy does not re-aggregate history.

Also removes an N+1: the rollup loop resolved each URL by short code
individually. `get_url_ids_by_short_codes()` resolves the batch.

### Auth — a rejected refresh left a dead cookie in the browser for 7 days

**File:** `backend/src/identity/routes/auth.py`

`POST /auth/refresh` raised on failure. **Raising discards the injected
`Response` and its headers**, so the `delete_cookie` calls never reached the
client. The cookie is httpOnly — JS can neither read nor delete it — so it was
replayed on every subsequent request, and each replay consumed the per-IP
`refresh` rate-limit budget, letting one stuck client throttle that user's own
next sign-in.

The rejection is now a hand-built `JSONResponse` carrying the delete headers.
`_clear_auth_cookies` is shared with `logout` rather than duplicated.

**Note:** this is the second time in this file that "raise instead of return"
silently dropped response headers. If a handler must set a cookie *on the failure
path*, it must return a `Response`, never raise.

### Auth — wrong `current_password` answered 401 on an authenticated endpoint

**Files:** `identity/services/profile_service.py`, `shared/errors/auth.py`

`change_password` / `change_email` raised `InvalidCredentials` (401) while the
caller was *already authenticated*. The frontend reads 401 as "re-authenticate",
so it refreshed, re-sent the same wrong password, and reported **"Session
expired"** instead of naming the field — plus two audit rows for one user action.

New `IncorrectCurrentPassword(BadRequestError)` → 400. `InvalidCredentials` stays
401 because login genuinely has no session yet. This restores "401 means
re-authenticate" for every client.

### Webhooks — two circuit-breaker bugs

**File:** `backend/src/webhooks/services/webhook_service.py`

- `asyncio.create_task(deliver(...))` with no reference kept. The loop holds only
  a **weak** reference, so a delivery task was eligible for collection between
  scheduling and completion — a silently dropped webhook event. `_track()` now
  retains the task and logs its exception.
- The failure counter was only reset by a *successful* delivery, so a webhook
  that went down and stayed down counted forever and the breaker never closed —
  the endpoint had to be deleted and recreated. Now `(count, last_at)` with a
  300s window, and `_forget_webhook()` on delete.

### Infra — two module-level caches that could only grow

`shared/core/user_plan.py` (plan cache, no eviction → `_MAX_PLAN_CACHE_ENTRIES`
+ `_prune()`) and `deps.py` (the blacklist cache above). Same mistake both times:
a dict written on a miss and never revisited.

## Performance Batch 2 — OAuth Sign-In Instrumentation

### The 2s sign-in was a guess; now it is measurable

**File:** `backend/src/identity/services/auth_service.py`

The reported ~2s Google sign-in had **four** equally-valid explanations — two
HTTPS calls to the provider, a cold Neon connection (free tier suspends compute
after ~5 min idle), a Render cold start, or two Upstash round trips. Request-level
timing already existed (`tracing.py` logs `duration_ms` for every request) but a
single total cannot attribute cost, so nothing in the logs distinguished them.

`oauth_callback` now laps each phase and logs the breakdown unconditionally, on
success and failure:

```
oauth_callback timings provider=google total=1832ms redis_state_pkce=180ms
  provider_exchange=410ms db_lookup_by_sub=12ms db_audit_log=8ms
  mint_tokens=1ms redis_store_session=174ms
```

**Argon2 is timed separately from the INSERT.** A new OAuth user pays 100-300ms
for a hash that exists only so the account can also have a password. It runs in a
thread so it cannot block the loop, but it is still wall-clock, and it only
happens on a user's *first* sign-in — exactly when someone is timing how fast
sign-in feels. Folded into a `db_create` phase it would read as a slow database.

**Note:** the phases are **not** independent costs. A single large `db_*` phase
while the others are small is the signature of a cold connection, which is a
different fix from a slow provider. Do not sum the phases and treat the total as
attributable latency.

**No claim is made that the 2s is fixed.** Two Upstash round trips were removed
(one per OAuth leg, each of which was also a correctness fix) — a real but
unmeasured reduction. The dominant term is not yet identified; that needs one
production log line.

### FakeRedis must model every script, and dispatch on the script body

**File:** `backend/tests/test_core/test_auth_reuse_pkce.py`

`FakeRedis.eval` now models three scripts instead of two, matched on **script
text** rather than `numkeys` — the init and consume scripts are called with the
same `numkeys` and the same two keys, so only their bodies differ.

A real EVAL runs Lua; a double cannot. Returning one canned value for every
script hides shape changes: these scripts return different types (an int status,
a `[state, verifier]` pair, an int `1`) and take different argument shapes. A call
site that unpacked the wrong one, or passed keys where it should pass values,
passes against the double and fails in production. **When a fake cannot execute
the real thing, model it — do not return a canned value.**

## Frontend Batch 2 — False Empty States, Silently Truncated Lists

### An outage rendered as "no data" on seven pages

**Files:** `folders`, `tags`, `webhooks`, `webhooks/receiver`, `audit-logs`, `favorites`, `urls` pages

Every list page called `useQuery({ enabled: isReady })`. While a query is
**disabled**, v5 reports `isPending === true` but `isFetching === false` — so
`isLoading` (defined as `isPending && isFetching`) is **false**, and `isError` is
false because nothing has been fetched to fail. All three branches missed and the
page fell through to the empty state.

When the *gating* query failed, users saw **"No folders yet"** — a confident,
specific, wrong statement inviting them to create a duplicate. Fix per page:
`isPending` instead of `isLoading`, plus an explicit `wsError` branch, because a
failed gating query means the list query never runs and *its* `isError` is also
false. The error belongs to the query that actually failed.

**Note:** in v5, `isLoading` is not "has not loaded" — it is "pending *and*
fetching". For any `enabled: false` query it is permanently false. Prefer
`isPending`.

### Bulk operations always reported "0 URLs", and expiries died up to 5.5h early

**File:** `frontend/src/app/(authenticated)/bulk/page.tsx`

Each endpoint returns a **different** result key, but the page read
`result.updated`/`deleted`/`disabled` for all of them — disable and reactivate
always rendered "0".

Worse: the CSV `expires_at` column is **local wall-clock** and was labelled UTC
via `toISOString().slice(0, 16)`. Every bulk-created link with an expiry died up
to 5.5 hours early depending on the creator's timezone. Now `new Date(...).toISOString()`.

### 401 handling on endpoints where 401 is not a session problem

**File:** `frontend/src/lib/api.ts`

`apiFetch` treated every 401 as "expired" → refresh → retry → `/login`. Three
endpoints return 401 for unrelated reasons, each triggering a pointless refresh
and then a logout: `/auth/oauth/exchange` (invalid one-time code — single-use by
construction) and `/profile/*` (wrong current password). `NON_SESSION_401` lists
them, and the retry path now surfaces the server's real error via
`errorFromResponse()` instead of always saying "Session expired" — which is
exactly what made this class of bug invisible from the UI.

### `clearTokens()` could not clear anything

It called `localStorage.removeItem` for tokens that are httpOnly **cookies**. JS
can neither read nor delete an httpOnly cookie, so the function was a no-op that
looked like a fix. It is now empty with the reason inline — leaving a
plausible-looking dead function is what caused the original confusion. **Cookie
clearing must happen server-side.** (Do **not** "restore" this function.)

### List endpoints were silently truncated at 20

`urls.list()`, `auditApi.list()`, `webhookReceiverApi.list()` defaulted to the
server's default page size when called without an explicit `limit`. Favorites
resolved up to 100 ids and then fetched with no limit — so a user with 50
favorites saw 20, with no indication that 20 was not all of them.

Rather than patch three call sites (and hope a fourth is remembered),
`MAX_LIST_LIMIT = 100` is now the default **at the API choke point**, matching the
server ceiling. An explicit `limit` still wins.

### Assorted correctness

- `urls/page.tsx` header showed `items.length` — the size of the current **page** —
  as the workspace total. A 500-URL workspace read "5 URLs". Now `total`.
- `billing/page.tsx` invalidated `["authMe"]`, but the canonical shared key is
  `["me"]` (shared with `AuthPrefetcher` and `useMe`) — the invalidation hit
  nothing, so the plan badge stayed stale until a hard reload.
- The urls edit mutation did not invalidate `["urls"]`, so the list kept showing
  the pre-edit short code.
- `admin/page.tsx` could compute page 0 of a list it had just deleted the last
  item from; `setTotalUsers` was missing from two handlers that change the count.
- `sidebar.handleLogout` navigated to `/login` unconditionally; on a network error
  the session was still live, so the proxy bounced straight back to `/dashboard`.
  Now toasts and goes to `/login?expired=1`, which the proxy honours.
- `useUrls` had no `placeholderData`, so every filter keystroke blanked the table
  with "No URLs found". `placeholderData: (prev) => prev` holds the rows.

**Note:** `favorites-page.test.tsx` called `getByText("No favorites yet")`
synchronously. Under the old code the empty state is what a page shows whenever
its query has not resolved — *including mid-flight* — so the assertion passed
**because of** the bug it was meant to guard against. It now awaits, and a new
test pins the real invariant: the empty state must be **absent** while the query
is in flight.

## Security Audit Batch — OAuth Takeover, Rate-Limit IP, Admin Bootstrap, Dead Config

A full audit pass. Each entry lists the file(s), what was actually wrong, and why the fix is the fix. New tests pin every one of these.

### OAuth — GitHub sign-in was an account-takeover primitive

**Files:** `backend/src/identity/services/sso/github_oauth.py`, `backend/src/identity/services/auth_service.py`, `backend/src/identity/models/user.py`

`github_oauth.get_user_info` returned `verified_email = (email is not None)` — *"GitHub gave us an address, therefore it is verified"*. GitHub lets an account **hold** an address it has not verified, and `auth_service.oauth_callback` then resolved the caller **by email**. So: add the victim's address to your own GitHub account, sign in, and you get a session for the victim's account. Full takeover, from a public sign-up.

Fixed in two halves, because either alone is insufficient:
- **The provider reports the truth.** `get_user_info` now *always* fetches `/user/emails`, keeps only entries with GitHub's own `verified` flag, and prefers the verified primary. The `/user` endpoint's `email` field is **not** proof — it is only populated for public addresses and is still unverified.
- **Identity is the provider subject, never the email.** New `users.github_id` column (+ unique index) and `UserRepository.get_by_oauth_sub()`. The callback resolves the caller by subject first; email is only consulted to *find a pre-existing account to link*, and only once the address is known-verified. A **missing** `verified_email` claim counts as unverified (`is not True`), not as permissive.
- Also refuse to merge into an account already bound to a *different* provider, and reject deactivated users at the callback.

`is_verified` is set from a genuinely verified claim only. Tests: `tests/test_core/test_oauth_trust.py`.

**Note:** `REQUIRE_EMAIL_VERIFICATION` (default `False`) gates login on `is_verified`. It is off because `is_verified` is currently advisory and turning it on locks out every account registered before the check existed. **Product decision, flagged for the user.**

### Rate Limiting — every visitor shared one bucket (XFF ignored)

**Files:** `backend/src/shared/core/client_ip.py` (new), `shared/middleware/rate_limit.py`, `shared/middleware/audit.py`, `links/routes/redirect.py`, `webhooks/routes/webhook_receiver.py`

All four consumers read `request.client.host` directly. Uvicorn is deliberately **not** started with `--proxy-headers`, so behind Render that is the **proxy's** IP: one abusive client throttled the entire platform, and every audit row was stamped with the proxy address.

`--proxy-headers` was considered and **rejected** — it changes the semantics globally and would conflict confusingly with `TRUST_PROXY`, so the same header would be trusted in one place and not another. Instead: one shared resolver, used at every call site (each previously had its own partial copy).

`get_client_ip(request)`: when `TRUST_PROXY` is on, take the **rightmost** `X-Forwarded-For` entry (the one the trusted edge appended, hence the only one the edge vouched for) with a fallback to the socket peer. **Leftmost is client-controlled** — trusting it lets anyone spoof an address to escape limits or to frame someone else. When off, the header is ignored entirely. Tests: `tests/test_core/test_client_ip.py`.

**Note:** `TRUST_PROXY` is load-bearing and stays. Removing it would be the fix for the wrong bug.

### Admin — anyone could become superadmin; the last admin could delete themselves

**Files:** `backend/src/admin/routes/admin.py`, `admin/services/admin_service.py`, `identity/models/user.py`, `shared/core/config.py`

- `POST /admin/seed` was reachable by **any authenticated user** — on a fresh database the first account to register owns the platform. Now requires `X-Admin-Bootstrap-Token` matched with `hmac.compare_digest` against `ADMIN_BOOTSTRAP_TOKEN`. **Empty (the default) disables the endpoint with a 404** — better than a check that fails open.
- New `users.is_active` (indexed) suspends an account without deleting it. `get_current_user` rejects inactive users on **both** the JWT and API-key branches; `login` / `refresh` / `oauth_callback` check it too. `PATCH /admin/users/{id}/toggle-active`.
- `toggle_superadmin` / `toggle_active` / `delete_user` now take `acting_user_id` and share one guard: you cannot demote/deactivate/delete **yourself**, and you cannot remove the **last active superadmin** (counted in the DB, same transaction as the write). `delete_user` also revokes the user's refresh family.
- Tests: `tests/test_core/test_admin_guards.py` (service level, no DB) + route tests in `tests/test_routes/test_admin_routes.py`.

### Config — `SECRET_KEY` could be blank in production; CI ran as production

**Files:** `backend/src/shared/core/config.py`, `.github/workflows/ci.yml`, `nightly.yml`, `backend/tests/testcontainers.py`, `backend/tests/e2e_env.py`, `backend/.env.example`

`SECRET_KEY` was allowed to be empty. Every JWT and every webhook HMAC would be signed with a publicly known key. `validate_secret_key` now **hard-fails** when `ENVIRONMENT == "production"` and only warns otherwise (so tests and local dev keep working).

Enabling that immediately broke CI — and the reason was itself a finding: **`ENVIRONMENT` was never set in CI, so every test run booted as `production`** (the config default). CI, the nightly workflow, `testcontainers.py`, and `e2e_env.py` now set `ENVIRONMENT=test` explicitly.

**Note:** when a guard you just added fires in CI, ask *why it was asleep* before relaxing it.

### Config — refresh cookie outlived the refresh JWT by 23 days

**Files:** `backend/src/shared/core/config.py`, `identity/routes/auth.py`

The cookie TTL was hard-coded (`7*24*3600`) while the token expiry was a separate setting (`30 * 24 * 60 * 60`). The browser kept a cookie the server would reject for three weeks. Both are now config-driven (`REFRESH_TOKEN_EXPIRE_DAYS=7`, `REFRESH_COOKIE_MAX_AGE`) with `validate_cookie_ttls` forbidding the cookie outliving the token.

**Note:** the **access** cookie intentionally outlives the access token (`ACCESS_COOKIE_MAX_AGE=604800` vs `ACCESS_TOKEN_EXPIRE_MINUTES=60`) — that is what makes silent refresh work. Do **not** "align" the two.

### Auth endpoints had no rate limiting

**File:** `backend/src/identity/routes/auth.py`

`login`, `refresh`, `forgot-password`, `reset-password`, `verify-email`, `oauth/exchange`, `oauth/{provider}` and `oauth/callback` now all go through `_enforce_auth_rate_limit(request, action)` with a per-action budget in `_AUTH_LIMITS` (e.g. login 10 burst / 1 per 10 s refill, forgot-password 5/10 min). Keyed on the shared client IP, so this inherits the XFF fix.

### `users.role` — a global permission column with zero readers

**Files:** `backend/src/identity/models/user.py`, `alembic/versions/c8d9e0f1a2b3_…py`, `frontend/src/lib/api.ts`, `frontend/src/store/auth.ts`, `frontend/src/app/(authenticated)/{profile,admin}/page.tsx`

Real authorization runs off `workspace_members.role`. `users.role` had **no readers** in the backend, yet the profile page displayed it as a "Role" row — a fake answer to a question the UI shouldn't have been asking. Column, `RoleEnum`, migration, and the two frontend render sites are gone.

Deleted as dead surface in the same pass: `shared/core/rbac.py`, `shared/middleware/rbac.py` (+ their 2 test files), and the `shared/core/event_dispatcher.py` shim (`conftest.py` now imports from `shared.events.dispatcher`).

`frontend/src/store/auth.ts` declared a **second, hand-copied** `User` interface that had already drifted; it now re-exports the API type, so there is one definition.

**Note:** migration `fa956e5f83aa` was left in place on purpose — deleting an applied revision breaks the alembic chain for any DB already at it.

### Auth — password/email changes didn't kill sessions or unlink providers

**Files:** `backend/src/identity/services/profile_service.py`, `auth_service.py`, `identity/services/session_revocation.py` (new)

- `change_password` and `reset_password` now revoke the **whole refresh family**, including the current session (security-correct, but a UX change: the user is signed out immediately).
- `change_email` clears `google_id` / `github_id` / `oauth_provider` — the provider's verified proof was for the *old* address, so keeping the link would let the old address sign back in.
- `login` / `refresh` / `logout` / `forgot_password` / `reset_password` / `verify_email` / `oauth_callback` / `change_password` now all write audit rows (login success **and** failure, and reuse detection).
- `revoke_refresh_family` / `is_family_revoked` moved into `identity/services/session_revocation.py` because `ProfileService` and `AdminService` need them too. `is_family_revoked` is **async** and fails **open** on a Redis error (fail-closed would turn a cache blip into a platform-wide logout).

**Note:** tests patching the Redis double must patch **both** `src.identity.services.auth_service.redis_client` and `src.identity.services.session_revocation.redis_client` — `tests/test_core/test_auth_reuse_pkce.py` has a `fake_redis()` helper that does this.

### Security — token claims could be overwritten by caller data

**File:** `backend/src/shared/core/security.py`

`create_access_token` / `create_refresh_token` shared one `_encode()` with a `_RESERVED_CLAIMS` guard, so a caller passing `{"exp": …}` or `{"type": …}` in `data` can no longer forge those claims. Refresh expiry is config-driven.

### Auth — `access_token` had no `jti`

Deliberately **not** added. An access-token denylist with no consumer is the same dead surface being removed in this batch; refresh reuse detection already covers the replayable credential.

### Auth endpoints return the user, so the client stops round-tripping

**Files:** `backend/src/identity/routes/auth.py`, `frontend/src/lib/api.ts`, `frontend/src/app/login/page.tsx`

`oauth_exchange` returns `TokenWithUser` (adds `user: UserResponse`) alongside the tokens. The login chain is now `exchangeOauth(code) → setUser(user) → redirect` — the extra `/auth/me` hop is gone (a request whose failure would strand the user *after* the one-time code is consumed).

### Favorites — no workspace access check on add

**File:** `backend/src/links/services/favorite_service.py`

`add` accepted any `url_id` and created the row, so you could favourite a URL in a workspace you have no access to. It now takes a (required) `WorkspaceRepository` and checks access first, returning `URLNotFound` (not "forbidden") so the endpoint is not an existence oracle for other tenants' URLs.

**Note:** `WorkspaceRepository.verify_access` **returns** `Workspace | None` — it does not raise. A bare `await repo.verify_access(...)` compiles, passes lint and typecheck, and silently checks nothing. The result must be tested. `workspace_repo` is a required constructor arg (not `| None = None`) so the guard cannot be quietly omitted by a future caller, and a `None` default would have made the check fail *open*. Tests: `tests/test_core/test_favorite_access.py`.

### Workspaces — accepting an invite silently verified your email

**File:** `backend/src/workspaces/services/workspace_service.py` function `accept_invite`

The method ended with:

```python
if not user.is_verified:
    await self.user_repo.update(user.id, is_verified=True)
```

An invite proves that *somebody else* knows an address, not that the person accepting owns the inbox. This was a **free bypass of email verification** — accept any invite and the flag flips, which would have quietly defeated `REQUIRE_EMAIL_VERIFICATION` the moment it was ever enabled. Same confused reasoning as the GitHub bug above: a third party's word was treated as proof of ownership.

Removed. `is_verified` is now written in exactly two places, both of which involve the actual owner of the inbox: `AuthService.verify_email` (clicked the emailed link) and `AuthService.oauth_callback` (provider reported a verified claim). `ProfileService.change_email` correctly resets it to `False`. Tests: `tests/test_core/test_invite_not_verification.py`.

**Note:** the profile page renders an "Email not verified — check your inbox" card with a working "Resend" button wired to `POST /auth/resend-verification` (authenticated). The *unauthenticated* recovery — for users the login gate locks out *before* they can reach that endpoint — is `POST /auth/verify-email/resend` (see Audit Batch 3). If SMTP is misconfigured the email is *silently* dropped — `EmailService._send` logs "Would send email to…" and returns — so get the 503 surfaced by both resend endpoints rather than a permanent card that promises a mail which never arrives. Set up SMTP *before* ever flipping `REQUIRE_EMAIL_VERIFICATION`.

### Email — Forgot Password Spinner Never Stopped (SMTP hang, no timeout)

**File:** `backend/src/identity/services/email_service.py`, `backend/render.yaml`

Symptom: forgot-password button stuck on "Sending..." forever, no mail, no error. Not a UI bug — the HTTP request genuinely never completed.

`smtplib.SMTP(cls.SMTP_HOST, cls.SMTP_PORT)` was constructed with **no `timeout`**. An unreachable or stalling SMTP server blocks the worker thread indefinitely; `asyncio.to_thread` cannot cancel it, so the coroutine never resumes and the response never goes out. Fixed with `timeout=SMTP_TIMEOUT_SECONDS` on the constructor (covers DNS + TCP + the SMTP greeting) **and** `asyncio.wait_for(..., timeout=...)` as an outer ceiling, plus `SMTP_TIMEOUT_SECONDS: float = 10.0`.

Two things made this invisible before:

- **The exception handler caught everything** and only logged, so even a *fast* failure returned "a reset link has been sent" with a dead inbox. SMTP could be entirely broken with no symptom anywhere but a log nobody reads. Failures are still swallowed — a caller must not learn whether an address exists — but the timeout means they now arrive at a known time.
- **`render.yaml` listed no SMTP vars at all.** Mail worked only because they had been added by hand in the Render dashboard; a service created fresh from the file would have had none. Added, plus `ADMIN_BOOTSTRAP_TOKEN` and `REQUIRE_EMAIL_VERIFICATION`.

Also `normalize_smtp_password()` strips whitespace from the password. Gmail displays app passwords in 4-char groups (`abcd efgh ijkl mnop`); pasted with those spaces, `server.login()` fails 535 — silently, given the catch-all above. Applied in `is_configured()` as well, so a whitespace-only value reads as unconfigured rather than as a valid-looking one.

**Note:** change-password "working" proves nothing about SMTP — that path never sends mail, it only returns tokens. The only real proof is a mail actually arriving.

Tests: `tests/test_core/test_email_delivery.py`. The stall test releases via `threading.Event`, not `sleep` — `to_thread` cannot cancel, so a sleeping thread would keep the executor busy and `asyncio.run` would block on it at teardown (passing, but 30s slow).

### Docker Compose — `redis` had no healthcheck while everything gated on it

**File:** `docker/docker-compose.yml`

`backend` and the workers use `depends_on: redis: condition: service_healthy`, but `redis` declared no `healthcheck` — so compose waited forever and the stack never started. Added `redis-cli ping` (postgres and mongodb already had one).

---

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

## Auth Store — Dashboard Never Hydrated `user` (no Logout button)

**File:** `frontend/src/lib/auth-prefetcher.tsx`

The auth store was only populated by per-page `auth.me().then(setUser)` effects; `/dashboard` reads `user` but never sets it. An already-signed-in user (valid cookie) bounced from `/login` → `/dashboard` via the proxy and landed with `user` null → the sidebar rendered **no user/logout section** (it's gated on `{user && …}`), so they were stuck with no way out. Every other authenticated page happened to call `setUser`; the dashboard didn't.

**Fix:** `AuthPrefetcher` (rendered once in the `(authenticated)` layout) now runs a `useQuery(["me"])` whose queryFn calls `setUser(user)`, hydrating the store on **every** authenticated page — the logout button now appears regardless of entry path. `retry: false` + `staleTime: 5min` (same as the old prefetch). Page-level `setUser` calls are now redundant but harmless. Test in `src/test/auth-prefetcher.test.tsx` covers hydration + error → store stays empty.

**Defense in depth:** the Logout button in `frontend/src/components/layout/sidebar.tsx` is rendered **outside** the `{user && …}` gate (the user card / "Enable Admin Panel" stay gated). A signed-in user is never stranded even if `me()` fails transiently or hydration hasn't finished — there is always an escape hatch. `sidebar.test.tsx` asserts Logout renders when `user` is `null`.

## Testcontainers — `Settings()` Rebuilt Too Early (CI "localhost:27017 refused")

**File:** `backend/tests/testcontainers.py` function `start_containers`

`config.settings` was rebuilt with `Settings()` right after `DATABASE_URL` was set, but **before** `MONGODB_URI` / `REDIS_URL` were written to the environment. pydantic-settings keeps the already-constructed defaults, so `init_mongodb()` used `mongodb://admin:adminpassword@localhost:27017` (the default) instead of the container's mapped port.

- **Locally this was masked** by a stray local MongoDB on `127.0.0.1:27017` — Mongo tests "passed" against it, not the container.
- **On GitHub runners** it failed deterministically: 5 × `pymongo.errors.ServerSelectionTimeoutError: localhost:27017: Connection refused` in `test_workers.py`.

**Fix:** set ALL of `DATABASE_URL`, `MONGODB_URI`, `REDIS_URL` (and `_USE_TESTCONTAINERS`) first, then rebuild `config.settings = Settings()` as the last step of `start_containers()`.

Related noise: `reset_pooled_engine` in `tests/test_workers.py` disposes the shared app engine whose asyncpg connections live on earlier function-scoped loops → asyncpg logs benign `RuntimeError: Event loop is closed` / "attached to a different loop" (GitHub surfaced these as 10× error annotations). The fixture suppresses the `sqlalchemy.pool` logger during dispose.

## Testcontainers — Route Tests Hit Production Upstash (rate-limit state leaked)

**File:** `backend/tests/testcontainers.py` function `start_containers`

A sibling of the `Settings()` bug above: the redis *container* was started and `REDIS_URL` set, but `_build_redis_client()` **prefers the Upstash REST client whenever BOTH `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` are set — and `backend/.env` ships them**. `REDIS_URL` pointing at the container was not enough. Every testcontainers route test therefore evaluated rate limits, idempotency markers, and session state against the **real production Upstash cache**.

It was invisible for two reasons. `upstash_redis.asyncio.Redis` is *also* named `Redis`, so a `type(client).__name__` check read "plain Redis" — you must check `RedisAdapter._is_upstash`, not the class name. And the existing route tests' rate-limit budgets are generous (login 10 burst / refresh 60), so a few runs to the shared production bucket never tripped them.

What surfaced it: `verify_email_resend` has a **5-per-5-min** budget (it is an unauthenticated mail cannon). After a few runs, the production bucket `rl:auth:verify_email_resend:127.0.0.1` sat at `tokens: 0.94` with a ~1-day TTL — and every subsequent test run 429'd, deterministically, on its *first* call, even in complete isolation.

**Fix:** `start_containers()` now blanks `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` (empty string has pydantic-settings env precedence over the `.env` copies) *before* the `Settings()` rebuild. Since `pytest_sessionstart` runs before any test module imports `src.shared.core.redis`, the first `import` builds the plain-Redis adapter against the container — no singleton rebinding needed. The two vars joined `_MANAGED_ENV` so a failed start still restores them. Route tests now pass repeatedly in one session and across sessions.

**Note:** the `"testclient"` host never appears — the ASGI test transport presents `127.0.0.1`, so rate-limit keys for route tests are `rl:*:127.0.0.1:...`. When debugging a test-created key, look there, not for the hostname.

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

**File:** `backend/src/analytics/workers/aggregation_worker.py` (includes cleanup purge), `backend/src/webhooks/workers/webhook_retry_worker.py`, `backend/src/shared/workers/kafka_consumer_pool.py`

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
```

## Start Frontend
```
cd frontend
npm run dev
```

## E2E / Integration Test Layers

All run only with Docker available (each boots Postgres 16 + Mongo 7 + Redis 7 testcontainers and **never** touches `.env` production services). Do not run them while another app is squatting on `127.0.0.1:8000`.

**Backend E2E** — real uvicorn process (:8001) driven over real HTTP:
```
cd backend
uv run pytest tests/test_e2e -v --use-testcontainers
```

**Frontend integration** — vitest (node env, in-test cookie jar) against the real backend:
**Frontend E2E** — Playwright browser against the real backend via the Next proxy.
Both need the standalone backend running on `127.0.0.1:8000` (the frontend `BACKEND_URL` default):
```
cd backend
uv run python scripts/e2e_server.py          # E2E_PORT to override the port
# then, in a second terminal:
cd frontend
npm run test:integration                     # vitest integration config
npm run test:e2e:real                        # playwright.real.config.ts
```

`scripts/e2e_server.py` and `tests/test_e2e/conftest.py` both boot uvicorn with an env scrubbed by `tests/e2e_env.py` (SMTP, Upstash Redis, OTLP/New Relic, Kafka bootstrap, SECRET_KEY) so a subprocess can never reach real external services — the isolated env is the whole point, since `mock_external_services`/`fast_password_hashing` patches do NOT cross process boundaries. Kafka fails fast against `127.0.0.1:1`; the lifespan logs and continues.

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

# Performance Batch — Latency / Async / Query Optimizations

## OAuth Sign-In — Serial Redis Round Trips on the Callback

**File:** `backend/src/identity/services/auth_service.py`, `backend/src/shared/core/redis.py`

`oauth_callback` did four serial Redis operations (`state get` → `state delete` → `pkce get` → `pkce delete`). With Upstash REST each HTTPS request is ~100-200ms, so the callback added ~400-800ms of pure serial latency on top of the provider round trip.

**Fix:** `RedisAdapter` gained `mget(*keys)` / `delete_many(*keys)` (Upstash batched `MGET`/`DEL` commands vs local pipelined variants). The callback now does `mget(oauth:state, oauth:pkce)` then `delete_many(...)` — two round trips total. **Always batch related Upstash ops — one REST call per HTTPS request.**

## OAuth Exchange — Extra `/auth/me` Hop After Handoff

**File:** `backend/src/identity/routes/auth.py`, `backend/src/identity/schemas/user.py`

After `POST /oauth/exchange` the login page called `auth.me()` — one more network round trip before redirect.

**Fix:** exchange now returns `TokenWithUser` (adds `user: UserResponse`) alongside the tokens. Login chain: `exchangeOauth(code) → setUser(user) → redirect` (the `auth.me()` call was removed from the chain).

## Argon2 Hashing — Blocked the Event Loop

**File:** `backend/src/shared/core/security.py` + all call sites

`passlib`'s Argon2 is CPU-bound (≈100-300ms); the sync `hash_password`/`verify_password` blocked the event loop on register/login/reset/API-key-auth/redirect-password/URL-create/bulk-create/profile-change.

**Fix:** added `hash_password_async`/`verify_password_async` (`asyncio.to_thread`). All async call sites (`auth_service`, `profile_service`, `url_service`, `bulk_service`, `api_key_service`, `api_key_auth`, `deps`, `redirect_service`) use the async variants; the sync wrappers remain only as the thread-pool targets.

## Workspace Access — Two Queries Down to One

**File:** `backend/src/workspaces/repositories/workspace_repository.py` functions `verify_access` / `verify_role`

Both did a sequential owner SELECT then a member SELECT. Now single outer-join queries (owner OR membership in one round trip; `verify_role` selects `(owner_id, role)` and resolves the hierarchy in Python). The owner is authoritative even if a membership row exists.

## Mongo Analytics — Missing Compound Indexes

**File:** `backend/src/shared/core/click_event.py`

Analytics range aggregations filter `(short_code, clicked_at)` and `(workspace_id, clicked_at)` but only single-field indexes existed. Added `short_code_clicked_at_idx` and `workspace_id_clicked_at_idx` (Beanie creates them on startup via `init_mongodb`).

## Alias Existence — Loaded a Full Row for a Boolean

**File:** `backend/src/links/repositories/url_repository.py` function `alias_exists`

Was `SELECT * FROM urls ...` then discarded the row. Now `EXISTS(subquery)` returns a scalar boolean — the DB stops after the first match.

## API-Key Quota — N+1 Round Trips on the Dashboard

**Files:** `backend/src/identity/services/api_key_service.py`, `backend/src/identity/routes/api_keys.py`, `backend/src/identity/schemas/api_key.py`, `frontend/src/hooks/useDashboard.ts`, `frontend/src/lib/api.ts`

`useDashboard` fired `GET /api-keys/{id}/quota` once per active key (N+1 over Upstash/Redis). 

**Fix:** new `GET /api-keys/quota-summary` → `APIKeyAggregateQuota { used, limit, remaining, resets_at }`. `api_key_service.get_aggregate_quota` reads the per-key Redis counters in **one** `mget` (all active keys) and sums them, capped at the plan limit. The dashboard does one call. **Register static paths like `/quota-summary` anywhere — there is no `GET /{id}` route that could shadow it — but keep static-before-parameterized as the general rule.**

## Frontend Caching — Zero Staleness Caused Refetch Storms

**Files:** `frontend/src/lib/providers.tsx`, `frontend/src/queries/index.ts`

Global query `staleTime` was `0` → every mount and window-focus refetched everything. Bumped the default to 30s. `useMe` now sets `staleTime: 5min` + `retry: false`, matching `AuthPrefetcher` (they share the `["me"]` cache entry so the prefetcher and any `useMe` never double-fetch). Removed the `select: (data) => data` no-op in `useUrls`.

## Login Page — Cold-Start Prewarm

**Files:** `backend/src/main.py`, `frontend/src/app/login/page.tsx`

Render free tier + Neon sleep: the first request after idle can take seconds (DB wake) → slow login. Added `GET /api/v1/ping` (best-effort DB `check_db_health()` + Redis ping, **always 200**) and the login page fire-and-forgets `fetch("/api/v1/ping")` on mount while the user types credentials / picks a provider. `/health` still owns 503 reporting.
