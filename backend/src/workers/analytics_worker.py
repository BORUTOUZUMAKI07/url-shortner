import asyncio
import json
from datetime import datetime

from user_agents import parse

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.core.mongodb import init_mongodb
from src.documents.click_event import ClickEvent
from src.events.kafka import publish_raw
from src.events.schemas import deserialize
from src.log_utils import get_logger, setup_logging
from src.repositories import AnalyticsRepository, URLRepository
from src.workers._sni_patch import _make_sni_context
from src.workers.kafka_consumer_pool import KafkaConnectionPool


async def consume_url_clicked_events():
    setup_logging()
    from src.core.tracing import init_metrics, init_tracing
    init_tracing()
    init_metrics()
    logger = get_logger("analytics-worker")

    kwargs = {
        "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "security_protocol": settings.KAFKA_SECURITY_PROTOCOL,
        "group_id": "analytics-worker-v3",
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

    try:
        await init_mongodb()
        logger.info("MongoDB initialized")
    except Exception as e:
        logger.warning("MongoDB connection failed (analytics will retry): %s", str(e))

    kwargs_without_bootstrap = kwargs.copy()
    kwargs_without_bootstrap.pop('bootstrap_servers', None)
    pool = KafkaConnectionPool(settings.KAFKA_BOOTSTRAP_SERVERS, **kwargs_without_bootstrap)
    logger.info("Analytics Worker listening on 'url-clicked'...")

    await pool.safe_consume(
        topics=["url-clicked"],
        callback=lambda msg, consumer: handle_analytics_message(msg, consumer, logger),
        auto_commit=False
    )


async def handle_analytics_message(msg, consumer, logger):
    try:
        try:
            event_data = deserialize("url-clicked", msg.value)
        except Exception:
            event_data = json.loads(msg.value.decode("utf-8"))
        await process_event(event_data, logger)
        await consumer.commit()
    except Exception:
        logger.exception("Error processing event at offset %s", msg.offset)
        try:
            await publish_raw("dlq-url-clicked", msg.value, msg.key)
        except Exception as dlq_e:
            logger.error("Failed to send to DLQ: %s", str(dlq_e))
        await consumer.commit()


async def process_event(event_data: dict, logger):
    ua_string = event_data.get("user_agent")
    browser = os = device = None
    if ua_string:
        user_agent = parse(ua_string)
        browser = user_agent.browser.family
        os = user_agent.os.family
        device = user_agent.device.family

    click_kwargs = dict(
        short_code=event_data["short_code"],
        original_url=event_data.get("original_url", ""),
        workspace_id=event_data.get("workspace_id"),
        ip_address=event_data.get("ip_address"),
        user_agent=ua_string,
        referer=event_data.get("referer"),
        browser=browser, os=os, device=device,
        country=event_data.get("country"),
        city=event_data.get("city"),
        utm_source=event_data.get("utm_source"),
        utm_medium=event_data.get("utm_medium"),
        utm_campaign=event_data.get("utm_campaign"),
        clicked_at=datetime.fromisoformat(event_data["clicked_at"]) if "clicked_at" in event_data else datetime.utcnow(),
    )
    event_id = event_data.get("event_id")
    if event_id:
        click_kwargs["event_id"] = event_id
    click_event = ClickEvent(**click_kwargs)

    try:
        await click_event.insert()
    except Exception as e:
        if "duplicate key error" in str(e).lower():
            logger.info("Duplicate event_id %s ignored.", click_event.event_id)
            return
        raise

    async with AsyncSessionLocal() as db:
        url_repo = URLRepository(db)
        analytics_repo = AnalyticsRepository(db)
        url_id = await url_repo.get_url_id_by_short_code(event_data["short_code"])
        if not url_id:
            logger.warning("URL not found for short_code: %s", event_data["short_code"])
            return
        await analytics_repo.upsert_click(url_id, click_event.clicked_at)


if __name__ == "__main__":
    asyncio.run(consume_url_clicked_events())
