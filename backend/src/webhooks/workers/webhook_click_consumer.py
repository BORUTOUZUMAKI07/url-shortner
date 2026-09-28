import asyncio
import json

from sqlalchemy import select

from src.shared import get_logger, setup_logging
from src.shared.core.config import settings
from src.shared.core.database import AsyncSessionLocal
from src.shared.core.redis import redis_client
from src.shared.events.kafka import publish_raw
from src.shared.events.schemas import deserialize
from src.shared.workers._sni_patch import _make_sni_context
from src.shared.workers.kafka_consumer_pool import KafkaConnectionPool
from src.webhooks.models.webhook import Webhook
from src.webhooks.models.webhook_event import WebhookEvent
from src.webhooks.models.webhook_subscription import WebhookSubscription
from src.webhooks.services.webhook_service import deliver_single_webhook


async def consume_url_clicked_webhooks():
    setup_logging()
    from src.shared.core.tracing import init_metrics, init_tracing
    init_tracing()
    init_metrics()
    logger = get_logger("webhook-click-consumer")

    kwargs = {
        "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "security_protocol": settings.KAFKA_SECURITY_PROTOCOL,
        "group_id": "webhook-click-consumer-v3",
        "auto_offset_reset": "earliest",
        "enable_auto_commit": False,
        "session_timeout_ms": 45000,
        "heartbeat_interval_ms": 15000,
        "request_timeout_ms": 120000,
        "max_poll_interval_ms": 300000,
    }

    if settings.KAFKA_SASL_USERNAME:
        kwargs["sasl_mechanism"] = settings.KAFKA_SASL_MECHANISM
        kwargs["sasl_plain_username"] = settings.KAFKA_SASL_USERNAME
        kwargs["sasl_plain_password"] = settings.KAFKA_SASL_PASSWORD

    if settings.KAFKA_SSL_CA_PATH:
        kwargs["ssl_context"] = _make_sni_context(settings.KAFKA_BOOTSTRAP_SERVERS, settings.KAFKA_SSL_CA_PATH)

    kwargs_without_bootstrap = kwargs.copy()
    kwargs_without_bootstrap.pop('bootstrap_servers', None)
    pool = KafkaConnectionPool(settings.KAFKA_BOOTSTRAP_SERVERS, **kwargs_without_bootstrap)
    logger.info("Webhook Click Consumer listening on 'url-clicked'...")

    await pool.safe_consume(
        topics=["url-clicked"],
        callback=lambda msg, consumer: handle_webhook_click_message(msg, consumer, logger),
        auto_commit=False
    )


# Idempotency for click-webhook dispatch. The marker goes through two states on
# ONE key:
#
#   1. PROCESS_LOCK_SECONDS after the claim — a short lock held while the batch
#      is being delivered. A concurrent consumer (or a Kafka redelivery before
#      the offset commit lands) sees the key and skips.
#   2. DONE_TTL_SECONDS after success — setex() extends the same key into the
#      long completion marker, so replays within a week are suppressed.
#
# Two keys, or claim-forever, would each lose one of the two guarantees:
# a long claim made at the start stays set through a crash mid-delivery, and a
# redelivery would permanently skip the event; a bare "done" marker written
# after the work still has the check-then-act race at acquisition time. The
# short lock covers acquisition, the extension covers replay.
PROCESS_LOCK_SECONDS = 90
DONE_TTL_SECONDS = 7 * 24 * 3600


async def deliver_click_webhooks(event_data: dict, logger):
    workspace_id = event_data.get("workspace_id")
    if not workspace_id:
        return

    event_id = event_data.get("event_id")
    if event_id:
        idempotency_key = f"idempotency:webhook_click:{event_id}"
        try:
            # Atomic claim — the get and the set are one decision. See
            # RedisAdapter.setnx: get()+setex() let two consumers both read
            # "absent" and both deliver.
            claimed = await redis_client.setnx(idempotency_key, PROCESS_LOCK_SECONDS, "1")
        except Exception:
            claimed = None
            logger.warning("Redis unavailable for idempotency claim on event_id %s", event_id)
        if claimed is False:
            logger.info("Skipping duplicate webhook dispatch for event_id %s", event_id)
            return
    else:
        logger.debug("Missing event_id in click event (short_code=%s), skipping idempotency",
                       event_data.get("short_code"))
        idempotency_key = None

    click_payload = {
        "event": "url.clicked",
        "short_code": event_data.get("short_code"),
        "original_url": event_data.get("original_url"),
        "workspace_id": workspace_id,
        "ip_address": event_data.get("ip_address"),
        "user_agent": event_data.get("user_agent"),
        "referer": event_data.get("referer"),
        "country": event_data.get("country"),
        "city": event_data.get("city"),
        "utm_source": event_data.get("utm_source"),
        "utm_medium": event_data.get("utm_medium"),
        "utm_campaign": event_data.get("utm_campaign"),
        "clicked_at": event_data.get("clicked_at"),
    }

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Webhook).where(
                    Webhook.workspace_id == workspace_id,
                    Webhook.is_active == True,
                    Webhook.subscriptions.any(WebhookSubscription.event_type == "url.clicked"),
                )
            )
            webhooks = list(result.scalars().all())

            for wh in webhooks:
                success, code, error = await deliver_single_webhook(
                    wh.id, wh.url, wh.secret, click_payload, "url.clicked",
                )
                db.add(WebhookEvent(
                    webhook_id=wh.id,
                    event_type="url.clicked",
                    payload=json.dumps(click_payload),
                    status="delivered" if success else "failed",
                    response_code=code,
                    error=error,
                ))
                if success:
                    logger.info("Delivered url.clicked webhook %s -> %s (status %s)", wh.id, wh.url, code)
                else:
                    logger.warning("Failed to deliver url.clicked webhook %s -> %s: %s", wh.id, wh.url, error)

            await db.commit()
    except Exception:
        # Anything below the claim — a delivery failure, a dead DB connection,
        # a cancelled task — releases the lock, so a Kafka redelivery after
        # `auto_offset_reset=earliest` reprocessing retries the event instead of
        # permanently skipping it. The lock TTL is the backstop for a hard kill
        # that skips this line.
        if idempotency_key is not None:
            try:
                await redis_client.delete(idempotency_key)
            except Exception:
                logger.warning("Redis unavailable while releasing idempotency lock for event_id %s", event_id)
        raise

    if idempotency_key is not None:
        try:
            # Extend the short processing lock into the long completion marker.
            # Only success gets here, so the key now means "delivered", not
            # "in flight".
            await redis_client.setex(idempotency_key, DONE_TTL_SECONDS, "1")
        except Exception:
            logger.warning("Redis unavailable while marking webhook idempotency for event_id %s", event_id)


async def handle_webhook_click_message(msg, consumer, logger):
    try:
        try:
            event_data = deserialize("url-clicked", msg.value)
        except Exception:
            event_data = json.loads(msg.value.decode("utf-8"))
        await deliver_click_webhooks(event_data, logger)
        await consumer.commit()
    except Exception:
        logger.exception("Error processing webhook click event at offset %s", msg.offset)
        try:
            await publish_raw("dlq-url-clicked", msg.value, msg.key)
        except Exception as dlq_e:
            logger.error("Failed to send to DLQ: %s", str(dlq_e))
        await consumer.commit()


if __name__ == "__main__":
    asyncio.run(consume_url_clicked_webhooks())
