"""Environment for E2E servers: keeps a real uvicorn process away from production infra.

The uvicorn subprocess is a *separate* process from pytest/vitest, so the
`mock_external_services` / `fast_password_hashing` patches do NOT apply to it.
It constructs its own `Settings()` from the inherited env AND any local
`backend/.env` file (which points at real Neon/Atlas/Upstash/New Relic
credentials). Every real-*.py path must be blanked here so the server only
talks to the testcontainers that `start_containers()` wired into the env.
"""
from __future__ import annotations

import os

E2E_SECRET = "e2e-insecure-secret"


def build_e2e_env() -> dict[str, str]:
    env = dict(os.environ)
    # Skip embedded Kafka consumers/workers (they hang or spam retry logs).
    env["STANDALONE_WORKERS"] = "1"
    # Never send real email from an E2E server (e.g. workspace invites).
    env["SMTP_HOST"] = ""
    env["SMTP_USER"] = ""
    env["SMTP_PASSWORD"] = ""
    # Force the plain-Redis fallback path instead of the production Upstash REST client.
    env["UPSTASH_REDIS_REST_URL"] = ""
    env["UPSTASH_REDIS_REST_TOKEN"] = ""
    # No OTLP export to a real New Relic account.
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = ""
    env["OTEL_EXPORTER_OTLP_HEADERS"] = ""
    # Fail Kafka connect fast instead of spinning against the Aiven trial host
    # (whose free trial has long expired) — connection refused is instant, the
    # retry loop adds ~15s of backoff, then lifespan logs and continues.
    env["KAFKA_BOOTSTRAP_SERVERS"] = "127.0.0.1:1"
    env["SCHEMA_REGISTRY_URL"] = ""
    # Sign JWTs/webhook secrets with a deterministic test key, never the .env one.
    env["SECRET_KEY"] = E2E_SECRET
    env["WEBHOOK_SECRET_KEY"] = E2E_SECRET
    return env
