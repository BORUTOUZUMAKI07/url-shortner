#!/usr/bin/env python3
"""
Main entry point for starting the URL Shortener backend.

This script handles:
1. Setting up logging
2. Initializing databases (PostgreSQL, MongoDB, Redis)
3. Starting Kafka consumers for message processing
4. Starting scheduled cleanup workers

All Kafka workers now use a connection pool with exponential backoff
to handle intermittent connection drops gracefully.
"""

import os
import sys
from pathlib import Path

# Ensure src/ is importable when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.core.database import engine
from src.core.mongodb import init_mongodb
from src.core.redis import init_redis
from src.core.tracing import init_metrics, init_tracing, instrument_fastapi, instrument_sqlalchemy
from src.errors.base import AppError
from src.events.kafka import close_kafka, init_kafka
from src.log_utils import get_logger, setup_logging
from src.middleware.audit import AuditContextMiddleware
from src.middleware.metrics import MetricsMiddleware
from src.middleware.rate_limit import RateLimitMiddleware
from src.middleware.rbac import RBACMiddleware
from src.middleware.tracing import TracingMiddleware
from src.routes import (
    admin,
    analytics,
    api_keys,
    audit_logs,
    auth,
    billing,
    bulk,
    favorites,
    folders,
    profile,
    redirect,
    tags,
    urls,
    webhook_receiver,
    webhooks,
    workspaces,
)
from src.workers.aggregation_worker import start_worker as start_aggregation_worker
from src.workers.analytics_worker import consume_url_clicked_events
from src.workers.cleanup_worker import start_worker as start_cleanup_worker
from src.workers.expiry_worker import start_worker as start_expiry_worker
from src.workers.metadata_worker import consume_url_created
from src.workers.webhook_click_consumer import consume_url_clicked_webhooks
from src.workers.webhook_retry_worker import start_worker as start_webhook_retry_worker


def create_app(lifespan_override=None):
    app = FastAPI(
        title="URL Shortener",
        description="Enterprise URL Shortener API",
        version="1.0.0",
        lifespan=lifespan_override,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Configure middleware (order matters)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuditContextMiddleware)
    app.add_middleware(TracingMiddleware)
    app.add_middleware(RBACMiddleware)

    # Exception handlers
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "error_code": exc.error_code},
        )

    # Include routers
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(urls.router, prefix="/api/v1")
    app.include_router(profile.router, prefix="/api/v1")
    app.include_router(workspaces.router, prefix="/api/v1")
    app.include_router(favorites.router, prefix="/api/v1")
    app.include_router(folders.router, prefix="/api/v1")
    app.include_router(tags.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(analytics.router, prefix="/api/v1")
    app.include_router(api_keys.router, prefix="/api/v1")
    app.include_router(audit_logs.router, prefix="/api/v1")
    app.include_router(billing.router, prefix="/api/v1")
    app.include_router(bulk.router, prefix="/api/v1")
    app.include_router(webhook_receiver.router, prefix="/api/v1")
    app.include_router(webhooks.router, prefix="/api/v1")
    app.include_router(redirect.router, tags=["redirect"])

    return app


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    setup_logging()
    logger = get_logger()

    # Silence noisy aiokafka reconnection retry logs (these are automatic retries, not real errors)
    import logging as _logging
    _logging.getLogger("aiokafka").setLevel(_logging.ERROR)
    _logging.getLogger("aiokafka.conn").setLevel(_logging.ERROR)
    _logging.getLogger("aiokafka.consumer").setLevel(_logging.ERROR)
    _logging.getLogger("aiokafka.producer").setLevel(_logging.ERROR)

    try:
        init_tracing()
        init_metrics()
    except Exception as e:
        print(f"[WARNING] Tracing/metrics init failed: {e}")

    # Initialize databases
    try:
        await init_redis()
        print("[OK] Redis (Upstash) connected successfully.")
    except Exception as e:
        print(f"[WARNING] Redis connection failed: {e}")

    try:
        await init_mongodb()
        print("[OK] MongoDB (Atlas) connected successfully.")
    except Exception as e:
        print(f"[WARNING] MongoDB connection failed: {e}")

    try:
        await init_kafka()
        print("[OK] Kafka connected successfully.")
    except Exception as e:
        print(f"[WARNING] Kafka connection failed (consumers will retry): {e}")

    # Start background workers (skip if running them separately)
    if not os.environ.get("STANDALONE_WORKERS"):
        logger.info("Starting URL Shortener workers...")

        analytics_task = asyncio.create_task(consume_url_clicked_events())
        metadata_task = asyncio.create_task(consume_url_created())
        webhook_click_task = asyncio.create_task(consume_url_clicked_webhooks())
        webhook_retry_task = asyncio.create_task(start_webhook_retry_worker())
        aggregation_task = asyncio.create_task(start_aggregation_worker())
        expiry_task = asyncio.create_task(start_expiry_worker())
        cleanup_task = asyncio.create_task(start_cleanup_worker())

        yield

        logger.info("Shutting down URL Shortener workers...")
        for task in [analytics_task, metadata_task, webhook_click_task, webhook_retry_task, aggregation_task, expiry_task, cleanup_task]:
            task.cancel()
        await asyncio.gather(*[task if task.done() else asyncio.wait_for(task, timeout=5) for task in [analytics_task, metadata_task, webhook_click_task, webhook_retry_task, aggregation_task, expiry_task, cleanup_task]], return_exceptions=True)
    else:
        print("[INFO] Workers NOT started in backend (running separately)")
        yield

    await close_kafka()
    logger.info("Shutdown complete.")


app = create_app(lifespan_override=lifespan)


if __name__ == "__main__":
    instrument_fastapi(app)
    instrument_sqlalchemy(engine)

    # Determine port from settings (default 8000)
    port = int(settings.PORT) if hasattr(settings, "PORT") else 8000

    print(f"Starting URL Shortener on port {port}...")
    print("Consumers: analytics, metadata, webhook-click")
    print("Scheduled workers: webhook-retry, aggregation, expiry, cleanup")

    # Start the application
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False,
        access_log=False,
    )
