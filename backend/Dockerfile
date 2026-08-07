FROM python:3.13-slim AS builder

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends python3-venv && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md .
RUN pip install --no-cache-dir --upgrade pip hatchling build wheel
COPY . .
RUN python -m build --wheel

FROM python:3.13-slim

WORKDIR /app
RUN addgroup --system --gid 1001 app \
    && adduser --system --uid 1001 --gid 1001 app
COPY --from=builder /app/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

# Alembic migrations are not part of the wheel (they'd collide with the
# installed `alembic` package at site-packages root), so copy them in from
# the builder stage. `alembic.ini` lives in the same place the entrypoint runs.
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONDONTWRITEBYTECODE=1
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request, os, sys; port = os.environ.get('PORT', '8000'); sys.exit(0 if urllib.request.urlopen(f'http://0.0.0.0:{port}/health',timeout=3).status==200 else 1)" || exit 1
CMD ["sh", "/app/entrypoint.sh"]
