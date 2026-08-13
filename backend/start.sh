#!/bin/sh
set -e

# Run migrations in the BACKGROUND so a cold/paused database (free-tier Neon
# pauses after inactivity) can't block the port bind and sink the deploy.
# uvicorn binds immediately and Render's port scan passes; once the DB is
# reachable, `alembic upgrade head` (a fast no-op when already at head)
# completes and the app serves traffic normally.
# Set SKIP_MIGRATIONS=1 to disable (e.g. when a separate migration job owns
# the schema).
if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
  echo "[start] running database migrations in background..."
  uv run alembic -c alembic.ini upgrade head &
fi

exec uv run uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}"
