import asyncio
import hashlib
import hmac
import json
import signal

import httpx
from sqlalchemy import select

from src.core.database import AsyncSessionLocal
from src.log_utils import get_logger, setup_logging
from src.models.dead_letter import DeadLetterEvent
from src.models.webhook import Webhook
from src.models.webhook_event import WebhookEvent
from src.services.webhook_service import decrypt_secret

MAX_RETRIES = 5
BASE_DELAY = 30
MAX_DELAY = 3600


def backoff_delay(retry_count: int) -> int:
    delay = BASE_DELAY * (2 ** (retry_count - 1))
    return min(delay, MAX_DELAY)  # type: ignore[no-any-return]


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
            wh = await db.get(Webhook, event.webhook_id)
            if not wh or not wh.is_active:
                event.retry_count += 1
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
                event.status = "delivered"
                event.response_code = resp.status_code
                event.error = None
            except Exception as e:
                event.retry_count += 1
                event.error = str(e)
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
    from src.core.tracing import init_metrics, init_tracing
    init_tracing()
    init_metrics()
    logger = get_logger("webhook-retry-worker")
    logger.info("Webhook Retry Worker started (max_retries=%d, base_delay=%ds)", MAX_RETRIES, BASE_DELAY)
    loop = asyncio.get_event_loop()
    stop = asyncio.Event()

    for sig_name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            try:
                loop.add_signal_handler(sig, stop.set)
            except NotImplementedError:
                pass

    while not stop.is_set():
        try:
            await retry_failed_events(logger)
        except Exception as e:
            logger.warning("Error in webhook retry loop: %s", str(e))
        await asyncio.sleep(60)

    logger.info("Webhook Retry Worker stopped")


if __name__ == "__main__":
    asyncio.run(start_worker())
