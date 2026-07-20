import asyncio
import json
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.events.kafka import publish_raw
from src.events.schemas import deserialize
from src.log_utils import get_logger, setup_logging
from src.repositories import URLRepository
from src.workers._sni_patch import _make_sni_context
from src.workers.kafka_consumer_pool import KafkaConnectionPool


async def extract_metadata(url: str, logger) -> dict[str, str | None]:
    result: dict[str, str | None] = {"title": None, "description": None, "og_image": None}
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "LinkForgeBot/1.0"})
            if resp.status_code != 200:
                logger.warning("extract_metadata got status %s for %s", resp.status_code, url)
                return result
            soup = BeautifulSoup(resp.text, "html.parser")

            if soup.title:
                result["title"] = soup.title.string.strip()[:500] if soup.title.string else None

            meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
            if meta_desc and meta_desc.get("content"):  # type: ignore[union-attr]
                result["description"] = meta_desc["content"].strip()[:1000]  # type: ignore[union-attr, index]

            og_image = soup.find("meta", attrs={"property": "og:image"})
            if og_image and og_image.get("content"):  # type: ignore[union-attr]
                raw = og_image["content"].strip()  # type: ignore[union-attr, index]
                parsed = urlparse(raw)
                if parsed.scheme:
                    result["og_image"] = raw
                else:
                    result["og_image"] = str(urlparse(url).scheme) + "://" + str(urlparse(url).netloc) + raw
    except Exception as e:
        logger.warning("Failed to extract metadata from %s: %s", url, e)
    return result


async def consume_url_created():
    setup_logging()
    from src.core.tracing import init_metrics, init_tracing
    init_tracing()
    init_metrics()
    logger = get_logger("metadata-worker")

    kwargs = {
        "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "security_protocol": settings.KAFKA_SECURITY_PROTOCOL,
        "group_id": "metadata-worker-v3",
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
    logger.info("Metadata Worker listening on 'url-created'...")

    await pool.safe_consume(
        topics=["url-created"],
        callback=lambda msg, consumer: handle_metadata_message(msg, consumer, logger),
        auto_commit=False
    )


async def handle_metadata_message(msg, consumer, logger):
    try:
        try:
            event_data = deserialize("url-created", msg.value)
        except Exception:
            event_data = json.loads(msg.value.decode("utf-8"))

        short_code = event_data.get("short_code")
        original_url = event_data.get("original_url")
        if not short_code or not original_url:
            logger.warning("Missing short_code or original_url in event")
            await consumer.commit()
            return

        assert isinstance(short_code, str)
        assert isinstance(original_url, str)
        logger.info("Extracting metadata for %s (%s)", short_code, original_url)
        meta = await extract_metadata(original_url, logger)

        if meta["title"] or meta["description"] or meta["og_image"]:
            async with AsyncSessionLocal() as db:
                url_repo = URLRepository(db)
                url_obj = await url_repo.get_by_short_code(short_code)
                if url_obj:
                    await url_repo.update(url_obj.id, **meta)
                    logger.info("Metadata stored for %s: title=%s", short_code, meta["title"])
                else:
                    logger.warning("URL not found for short_code: %s", short_code)

        await consumer.commit()
    except Exception as e:
        logger.exception("Error processing metadata event at offset %s: %s", msg.offset, str(e))
        try:
            await publish_raw("dlq-url-created", msg.value, msg.key)
        except Exception as dlq_e:
            logger.error("Failed to send to DLQ: %s", str(dlq_e))
        await consumer.commit()


if __name__ == "__main__":
    asyncio.run(consume_url_created())
