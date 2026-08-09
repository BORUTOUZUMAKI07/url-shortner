import asyncio
import hashlib
import hmac
import json
import time

import httpx
from sqlalchemy import select

from src.analytics.models.dead_letter import DeadLetterEvent
from src.shared import get_logger, setup_logging
from src.shared.core.database import AsyncSessionLocal
from src.shared.core.redis import redis_client
from src.shared.workers.shutdown import install_signal_handlers, wait_for_shutdown
from src.webhooks.models.webhook import Webhook
from src.webhooks.models.webhook_event import WebhookEvent
from src.webhooks.services.webhook_service import decrypt_secret

MAX_RETRIES = 5
BASE_DELAY = 30
MAX_DELAY = 3600


def backoff_delay(retry_count: int) -> int:
    delay = BASE_DELAY * (2 ** (retry_count - 1))
    return min(delay, MAX_DELAY)  # type: ignore[no-any-return]


def _last_attempt_key(event_id: int) -> str:
    return f"webhook_retry:{event_id}"


async def _mark_attempt(event) -> None:
    """Record when the event was last retried so backoff_delay can be enforced."""
    try:
        await redis_client.setex(_last_attempt_key(event.id), 2 * 3600, str(time.time()))
    except Exception:
        pass


async def _clear_attempt(event) -> None:
    try:
        await redis_client.delete(_last_attempt_key(event.id))
    except Exception:
        pass


async def _too_soon(event) -> bool:
    """True when the event's exponential backoff has not elapsed yet."""
    try:
        raw = await redis_client.get(_last_attempt_key(event.id))
        if not raw:
            return False
        return (time.time() - float(raw)) < backoff_delay(event.retry_count)
    except Exception:
        return False


async def retry_failed_events(logger):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WebhookEvent).where(
                WebhookEvent.status == "failed",
                WebhookEvent.retry_count < MAX_RETRIES,
            )
        )
        failed_events = result.scalars().all()

        if not failed_events:
            return

        logger.info("Found %d failed events to retry.", len(failed_events))

        for event in failed_events:
            # Respect the exponential backoff between attempts (previously the
            # constants existed but the worker retried everything every 60s).
            if await _too_soon(event):
                continue

            wh = await db.get(Webhook, event.webhook_id)
            if not wh or not wh.is_active:
                event.retry_count += 1
                await _mark_attempt(event)
                if event.retry_count >= MAX_RETRIES:
                    await _move_to_dlq(db, event, "Webhook inactive")
                    await db.delete(event)
                continue

            payload = json.loads(event.payload)
            secret = decrypt_secret(wh.secret)
            payload_bytes = event.payload.encode()
            signature = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        wh.url,
                        json=payload,
                        headers={
                            "Content-Type": "application/json",
                            "X-Webhook-Signature": signature,
                            "X-Webhook-Event": event.event_type,
                        },
                        timeout=10.0,
                    )
                if resp.is_success:
                    event.status = "delivered"
                    event.response_code = resp.status_code
                    event.error = None
                    await _clear_attempt(event)
                else:
                    event.retry_count += 1
                    event.response_code = resp.status_code
                    event.error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    logger.warning(
                        "Webhook %s returned %s for event %s (retry %d)",
                        wh.url, resp.status_code, event.event_type, event.retry_count,
                    )
                    await _mark_attempt(event)
                    if event.retry_count >= MAX_RETRIES:
                        await _move_to_dlq(db, event, event.error)
                        await db.delete(event)
            except Exception as e:
                event.retry_count += 1
                event.error = str(e)
                await _mark_attempt(event)
                if event.retry_count >= MAX_RETRIES:
                    await _move_to_dlq(db, event, str(e))
                    await db.delete(event)

        await db.commit()
        logger.info("Webhook retry scan complete.")


async def _move_to_dlq(db, event, error: str):
    dlq = DeadLetterEvent(
        topic=f"webhook:{event.event_type}",
        event_key=str(event.webhook_id),
        payload=event.payload,
        error=error,
        retry_count=event.retry_count,
    )
    db.add(dlq)


async def start_worker():
    setup_logging()
    from src.shared.core.tracing import init_metrics, init_tracing
    init_tracing()
    init_metrics()
    logger = get_logger("webhook-retry-worker")
    logger.info("Webhook Retry Worker started (max_retries=%d, base_delay=%ds)", MAX_RETRIES, BASE_DELAY)
    install_signal_handlers()

    while not await wait_for_shutdown():
        try:
            await retry_failed_events(logger)
        except Exception as e:
            logger.warning("Error in webhook retry loop: %s", str(e))
        try:
            await asyncio.wait_for(asyncio.shield(wait_for_shutdown()), timeout=60)
        except asyncio.TimeoutError:
            pass

    logger.info("Webhook Retry Worker stopped")


if __name__ == "__main__":
    asyncio.run(start_worker())
