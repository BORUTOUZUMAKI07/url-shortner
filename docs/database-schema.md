# LinkForge — Database Schema & Table Architecture

Entity-relationship diagram and per-table documentation for the PostgreSQL
schema (`backend/src/*/models/`). All tables are created and versioned by
[Alembic migrations](backend/alembic/).

## Entity Relationship Diagram

```mermaid
erDiagram
    users ||--o{ api_keys : "owns"
    users ||--o{ workspaces : "owns"
    users ||--o{ workspace_members : "member of"
    users ||--o{ favorites : "favorited"
    users ||--o{ urls : "created"
    users ||--o{ audit_logs : "acted as actor"

    workspaces ||--o{ urls : "contains"
    workspaces ||--o{ folders : "contains"
    workspaces ||--o{ tags : "contains"
    workspaces ||--o{ webhooks : "subscribes"
    workspaces ||--o{ workspace_members : "members"
    workspaces ||--o{ workspace_invites : "invites"
    workspaces ||--o{ audit_logs : "scoped to"

    urls ||--o{ url_analytics_summary : "has"
    urls ||--o{ favorites : "favorited by"
    urls ||--o{ url_tags : "tagged"
    urls ||--o{ webhook_events : "generates"
    urls ||o--|| folders : "in folder (optional)"
    urls }o--|| users : "owned by"
    urls }o--|| workspaces : "scoped to"

    folders }o--|| workspaces : "in"
    tags }o--|| workspaces : "in"
    tags ||--o{ url_tags : "used on"

    workspace_members }o--|| users : "user"
    workspace_members }o--|| workspaces : "workspace"

    workspace_invites }o--|| users : "invited by"
    workspace_invites }o--|| workspaces : "workspace invite"

    api_keys }o--|| users : "owned by"

    webhooks }o--|| workspaces : "belongs to"
    webhooks ||--o{ webhook_subscriptions : "subscribes to"
    webhooks ||--o{ webhook_events : "delivers"
    webhooks ||--o{ webhook_received_events : "received"

    webhook_subscriptions }o--|| webhooks : "subscription"

    url_tags ||--|| urls : "url"
    url_tags ||--|| tags : "tag"

    api_keys }o--|| users : "key"
```

## Table Catalog

### Core Identity

| Table | Description | Key Columns |
|---|---|---|
| `users` | Platform accounts (auth + OAuth) | `id`, `email`, `password_hash`, `is_active`, `is_superadmin`, `google_id`, `github_id`, `created_at` |
| `api_keys` | Programmatic access keys with daily quota | `id`, `user_id`, `name`, `prefix`, `key_hash`, `status`, `daily_requests_used`, `expires_at`, `created_at` |

**Relationships:** One user has many API keys. `api_keys.key_hash` stores an Argon2id hash — the raw key is never persisted.

---

### Multi-Tenancy (Workspaces)

| Table | Description | Key Columns |
|---|---|---|
| `workspaces` | Tenant isolation boundary | `id`, `name`, `owner_id`, `created_at` |
| `workspace_members` | Role-based membership in a workspace | `id`, `workspace_id`, `user_id`, `role` (admin/editor/viewer), `joined_at` |
| `workspace_invites` | Pending email invitations | `id`, `workspace_id`, `email`, `invited_by`, `token`, `role`, `status`, `expires_at`, `created_at` |

**Relationships:** A workspace has one owner and many members. Members hold `admin`, `editor`, or `viewer` roles. Invites are single-use tokens with TTL.

---

### URLs (the core resource)

| Table | Description | Key Columns |
|---|---|---|
| `urls` | Short links | `id`, `short_code`, `original_url`, `user_id`, `workspace_id`, `folder_id`, `custom_alias`, `domain`, `password_hash`, `is_ab_test`, `is_one_time`, `ios_url`, `android_url`, `expires_at`, `status` (active/disabled/deleted), `qr_code`, `title`, `description`, `og_image`, `created_at` |
| `folders` | Workspace-scoped folders | `id`, `name`, `workspace_id`, `created_at` |
| `tags` | Workspace-scoped tags | `id`, `name`, `workspace_id` |
| `url_tags` | Many-to-many URL ↔ Tag | `url_id`, `tag_id` (composite PK) |
| `favorites` | User-bookmarked URLs | `id`, `user_id`, `url_id`, `created_at` |

**Relationships:** A URL belongs to one user and one workspace, optionally one folder, and many tags. `custom_alias` is globally unique. `password_hash` is nullable — links without protection have `NULL`. `status` enables soft-delete without cascading immediately.

---

### Analytics (click events + rollups)

| Table | Description | Key Columns |
|---|---|---|
| `url_analytics_summary` | Cumulative rollup per URL (single writer) | `url_id` (PK), `total_clicks`, `unique_clicks`, `last_clicked_at` |
| `aggregation_watermarks` | Rollup cursor (advanced atomically with counters) | `key` (PK), `value` (timestamp) |

**Design note:** The rollup worker is the **single writer** of `url_analytics_summary`. It *adds* each 60s window to existing counters — never replaces — so cumulative totals can't collapse or double-count against the realtime path. The watermark lives in the same DB and is advanced in the same transaction as the rollup, making "rollup + advance" one indivisible step.

---

### Webhooks (outbound delivery)

| Table | Description | Key Columns |
|---|---|---|
| `webhooks` | Outbound webhook endpoints per workspace | `id`, `workspace_id`, `url`, `secret`, `is_active`, `created_at` |
| `webhook_subscriptions` | Events a webhook subscribes to | `id`, `webhook_id`, `event_type` (unique per webhook) |
| `webhook_events` | Outgoing delivery attempts | `id`, `webhook_id`, `event_type`, `payload`, `status`, `response_code`, `error`, `retry_count`, `created_at` |
| `webhook_received_events` | Inbound webhooks ingested by this service | `id`, `webhook_id`, `workspace_id`, `event_type`, `payload`, `headers`, `signature`, `signature_valid`, `source_ip`, `created_at` |

**Relationships:** One workspace has many webhooks. One webhook has many subscriptions (event types) and many delivery events.

---

### Audit & Dead Letter

| Table | Description | Key Columns |
|---|---|---|
| `audit_logs` | Immutable mutation trail | `id`, `actor_id`, `action`, `resource_type`, `resource_id`, `before_state`, `after_state`, `ip_address`, `user_agent`, `workspace_id`, `created_at` |
| `dead_letter_events` | Failed Kafka messages awaiting replay | `id`, `topic`, `event_key`, `payload`, `error`, `retry_count`, `created_at` |

**Relationships:** Audit logs reference actors and resources via `SET NULL` foreign keys — an audit entry survives even if its actor/workspace is deleted.

---

## Indexes (performance-critical)

| Table | Index | Purpose |
|---|---|---|
| `urls` | `short_code` (unique) | Redirect lookup — the hottest path in the app |
| `urls` | `custom_alias` (unique) | Custom alias resolution |
| `urls` | `workspace_id` | Workspace URL listing |
| `urls` | `expires_at` | Expiry scans / cleanup |
| `urls` | `user_id` | User-owned URL listing |
| `api_keys` | `prefix` | API-key authentication lookup |
| `webhook_events` | `status` | Retry queue polling |
| `workspace_members` | `(workspace_id, user_id)` (unique) | Membership lookup |
| `folders` | `(name, workspace_id)` (unique) | Folder name uniqueness per workspace |
| `tags` | `(name, workspace_id)` (unique) | Tag name uniqueness per workspace |
| `api_keys` | `user_id` | User's keys |
| `audit_logs` | `actor_id`, `resource_type`, `workspace_id` | Audit filtering |

---

## Enums

| Enum | Table | Values |
|---|---|---|
| `URLStatus` | `urls.status` | `active`, `disabled`, `deleted` |
| `APIKeyStatus` | `api_keys.status` | `active`, `revoked` |
| `InviteStatus` | `workspace_invites.status` | `pending`, `accepted`, `expired`, `cancelled` |
| `MemberRole` | `workspace_members.role` | `admin`, `editor`, `viewer` |

---

## On-Delete Behavior

| Parent → Child | FK Action | Rationale |
|---|---|---|
| `users` → `urls` | `CASCADE` | Deleting a user removes their links |
| `users` → `api_keys` | `CASCADE` | Keys belong to the user |
| `users` → `workspace_members` | `CASCADE` | Membership belongs to user |
| `users` → `favorites` | `CASCADE` | Favorites belong to user |
| `workspaces` → `urls/folders/tags/webhooks` | `CASCADE` | Workspace is the isolation boundary |
| `users` → `audit_logs` | `SET NULL` | Audit trail survives actor deletion |
| `workspaces` → `audit_logs` | `SET NULL` | Audit trail survives workspace deletion |
| `urls` → `url_analytics_summary` | `CASCADE` | Summary belongs to the URL |
| `urls` → `url_tags` | `CASCADE` | Junction table cleanup |
| `folders` → `urls` | `SET NULL` | URLs survive folder removal |
| `webhooks` → `webhook_events/subscriptions` | `CASCADE` | Belong to the webhook |
| `webhooks` → `webhook_received_events` | `SET NULL` | Received history survives webhook deletion |

---

## Migrations

All schema changes are versioned with Alembic in `backend/alembic/`. Run:

```bash
cd backend
uv run alembic upgrade head        # apply all pending migrations
uv run alembic revision --autogenerate -m "describe change"  # generate from model diff
```

The migration chain is linear (no branches). Fresh databases get the full schema automatically at boot via the entrypoint (`alembic upgrade head` → `uvicorn`).
