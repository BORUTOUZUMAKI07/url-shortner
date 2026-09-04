import asyncio
import json
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from src.analytics.models.dead_letter import DeadLetterEvent
from src.shared import get_logger, setup_logging
from src.shared.core.database import AsyncSessionLocal
from src.shared.core.redis import redis_client
from src.shared.workers.shutdown import install_signal_handlers, wait_for_shutdown
from src.webhooks.models.webhook import Webhook
from src.webhooks.models.webhook_event import WebhookEvent
from src.webhooks.services.webhook_service import deliver_single_webhook

MAX_RETRIES = 5
BASE_DELAY = 30
MAX_DELAY = 3600
BATCH_LIMIT = 100
_MAX_CONCURRENT_DELIVERIES = 5
_DLQ_RETENTION_DAYS = 30


def backoff_delay(retry_count: int) -> int:
    delay = BASE_DELAY * (2 ** (retry_count - 1))
    return min(delay, MAX_DELAY)  # type: ignore[no-any-return]


def _last_attempt_key(event_id: int) -> str:
    return f"webhook_retry:{event_id}"


async def _mark_attempt(event) -> None:
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
    try:
        raw = await redis_client.get(_last_attempt_key(event.id))
        if not raw:
            return False
        return (time.time() - float(raw)) < backoff_delay(event.retry_count)
    except Exception:
        return False


async def _retry_one_event(
    event: WebhookEvent,
    wh: Webhook,
    semaphore: asyncio.Semaphore,
    logger,
) -> tuple[WebhookEvent, bool, int | None, str | None]:
    """Deliver one retry attempt concurrently. Returns (event, success, code, error)."""
    if await _too_soon(event):
        return event, False, None, "backoff"
    async with semaphore:
        payload = json.loads(event.payload)
        success, code, error = await deliver_single_webhook(
            wh.id, wh.url, wh.secret, payload, event.event_type,
        )
        return event, success, code, error


async def retry_failed_events(logger):
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_DELIVERIES)

    # #3 — bounded batch with ordering; new DB session per invocation.
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WebhookEvent).where(
                WebhookEvent.status == "failed",
                WebhookEvent.retry_count < MAX_RETRIES,
            ).order_by(
                WebhookEvent.created_at.asc(),
            ).limit(BATCH_LIMIT)
        )
        failed_events = list(result.scalars().all())

        if not failed_events:
            return

        logger.info("Found %d failed events to retry.", len(failed_events))

        # Prefetch webhook data so we can load it outside the concurrent tasks.
        webhook_ids = {e.webhook_id for e in failed_events}
        webhooks: dict[int, Webhook] = {}
        for wid in webhook_ids:
            wh = await db.get(Webhook, wid)
            if wh and wh.is_active:
                webhooks[wid] = wh

        # #4 — concurrent delivery (bounded by semaphore).
        tasks = []
        for event in failed_events:
            wh = webhooks.get(event.webhook_id)
            if wh is None:
                # Webhook inactive or deleted — count toward retries.
                event.retry_count += 1
                await _mark_attempt(event)
                if event.retry_count >= MAX_RETRIES:
                    db.add(DeadLetterEvent(
                        topic=f"webhook:{event.event_type}",
                        event_key=str(event.webhook_id),
                        payload=event.payload,
                        error="Webhook inactive",
                        retry_count=event.retry_count,
                    ))
                    await db.delete(event)
                continue
            tasks.append(_retry_one_event(event, wh, semaphore, logger))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.warning("Retry task raised: %s", result)
                    continue
                event, success, code, error = result
                if error == "backoff":
                    continue
                if success:
                    event.status = "delivered"
                    event.response_code = code
                    event.error = None
                    await _clear_attempt(event)
                else:
                    event.retry_count += 1
                    event.response_code = code
                    event.error = error
                    await _mark_attempt(event)
                    logger.warning(
                        "Webhook %s returned %s for event %s (retry %d)",
                        event.webhook_id, code, event.event_type, event.retry_count,
                    )
                    if event.retry_count >= MAX_RETRIES:
                        db.add(DeadLetterEvent(
                            topic=f"webhook:{event.event_type}",
                            event_key=str(event.webhook_id),
                            payload=event.payload,
                            error=error or "Max retries exceeded",
                            retry_count=event.retry_count,
                        ))
                        await db.delete(event)

        await db.commit()
        logger.info("Webhook retry scan complete.")

    # #10 — periodic DLQ purge (runs every cycle, cheapDELETE).
    await _purge_old_dlq(logger)


async def _purge_old_dlq(logger):
    cutoff = datetime.now(timezone.utc) - timedelta(days=_DLQ_RETENTION_DAYS)
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import delete
            result = await db.execute(
                delete(DeadLetterEvent).where(DeadLetterEvent.created_at < cutoff)
            )
            if result.rowcount:
                await db.commit()
                logger.info("Purged %d DLQ events older than %d days", result.rowcount, _DLQ_RETENTION_DAYS)
    except Exception as e:
        logger.warning("DLQ purge failed: %s", e)


async def start_worker():
    setup_logging()
    from src.shared.core.tracing import init_metrics, init_tracing
    init_tracing()
    init_metrics()
    logger = get_logger("webhook-retry-worker")
    logger.info("Webhook Retry Worker started (max_retries=%d, base_delay=%ds, batch_limit=%d)",
                MAX_RETRIES, BASE_DELAY, BATCH_LIMIT)
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
