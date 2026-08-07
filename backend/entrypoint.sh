#!/bin/sh
set -e

# Run database migrations before starting the app so a fresh database
# gets the full schema automatically.
# Set SKIP_MIGRATIONS=1 to disable (e.g. when a separate migration job owns the schema).
if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
  echo "[entrypoint] running database migrations..."
  alembic -c alembic.ini upgrade head
fi

exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}"
