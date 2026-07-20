import asyncio
import hashlib
import hmac
import json

import httpx
from sqlalchemy import select

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.core.redis import redis_client
from src.events.kafka import publish_raw
from src.events.schemas import deserialize
from src.log_utils import get_logger, setup_logging
from src.models.webhook import Webhook
from src.models.webhook_event import WebhookEvent
from src.services.webhook_service import decrypt_secret
from src.workers._sni_patch import _make_sni_context
from src.workers.kafka_consumer_pool import KafkaConnectionPool


async def consume_url_clicked_webhooks():
    setup_logging()
    from src.core.tracing import init_metrics, init_tracing
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


async def deliver_click_webhooks(event_data: dict, logger):
    workspace_id = event_data.get("workspace_id")
    if not workspace_id:
        return

    event_id = event_data.get("event_id")
    if event_id:
        idempotency_key = f"idempotency:webhook_click:{event_id}"
        already_processed = await redis_client.get(idempotency_key)
        if already_processed:
            logger.info("Skipping duplicate webhook dispatch for event_id %s", event_id)
            return
        await redis_client.setex(idempotency_key, 86400 * 7, "1")
    else:
        logger.debug("Missing event_id in click event (short_code=%s), skipping idempotency",
                       event_data.get("short_code"))


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

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Webhook).where(
                Webhook.workspace_id == workspace_id,
                Webhook.is_active == True,
                Webhook.events.contains("url.clicked"),
            )
        )
        webhooks = list(result.scalars().all())

        for wh in webhooks:
            secret = decrypt_secret(wh.secret)
            payload_bytes = json.dumps(click_payload).encode()
            signature = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        wh.url,
                        json=click_payload,
                        headers={
                            "Content-Type": "application/json",
                            "X-Webhook-Signature": signature,
                            "X-Webhook-Event": "url.clicked",
                        },
                        timeout=10.0,
                    )
                db.add(WebhookEvent(
                    webhook_id=wh.id,
                    event_type="url.clicked",
                    payload=json.dumps(click_payload),
                    status="delivered",
                    response_code=resp.status_code,
                ))
                logger.info("Delivered url.clicked webhook %s -> %s (status %s)", wh.id, wh.url, resp.status_code)
            except Exception as e:
                db.add(WebhookEvent(
                    webhook_id=wh.id,
                    event_type="url.clicked",
                    payload=json.dumps(click_payload),
                    status="failed",
                    error=str(e),
                ))
                logger.warning("Failed to deliver url.clicked webhook %s -> %s: %s", wh.id, wh.url, str(e))

        await db.commit()


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
