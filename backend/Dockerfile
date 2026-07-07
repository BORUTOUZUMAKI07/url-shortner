FROM python:3.14-slim AS builder

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends python3-venv && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md .
RUN pip install --no-cache-dir --upgrade pip hatchling build wheel
COPY . .
RUN python -m build --wheel

FROM python:3.14-slim

WORKDIR /app
RUN addgroup --system --gid 1001 app \
    && adduser --system --uid 1001 --gid 1001 app
COPY --from=builder /app/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://0.0.0.0:8000/health',timeout=3).status==200 else 1)" || exit 1
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
