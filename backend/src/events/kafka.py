import asyncio
from typing import Optional

from aiokafka import AIOKafkaProducer

from src.core.config import settings
from src.events.schemas import serialize
from src.log_utils import get_logger
from src.workers._sni_patch import _make_sni_context

logger = get_logger(__name__)

producer: Optional[AIOKafkaProducer] = None

_RETRY_DELAYS = [1, 2, 4, 8, 16]  # exponential backoff seconds


async def init_kafka():
    global producer
    kwargs = {
        "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "security_protocol": settings.KAFKA_SECURITY_PROTOCOL,
    }
    if settings.KAFKA_SASL_USERNAME:
        kwargs["sasl_mechanism"] = settings.KAFKA_SASL_MECHANISM
        kwargs["sasl_plain_username"] = settings.KAFKA_SASL_USERNAME
        kwargs["sasl_plain_password"] = settings.KAFKA_SASL_PASSWORD  # type: ignore[assignment]
    if settings.KAFKA_SSL_CA_PATH:
        kwargs["ssl_context"] = _make_sni_context(
            settings.KAFKA_BOOTSTRAP_SERVERS, settings.KAFKA_SSL_CA_PATH,
        )
    for attempt, delay in enumerate(_RETRY_DELAYS):
        try:
            producer = AIOKafkaProducer(**kwargs)
            await producer.start()
            logger.info("Kafka Producer started successfully.")
            return
        except Exception as e:
            logger.warning("Kafka Producer start attempt %d failed: %s", attempt + 1, e)
            if attempt < len(_RETRY_DELAYS) - 1:
                await asyncio.sleep(delay)
            else:
                logger.error("Kafka Producer failed to start after %d attempts", len(_RETRY_DELAYS))
                raise


async def close_kafka():
    global producer
    if producer:
        await producer.stop()
        logger.info("Kafka Producer stopped.")


async def _send_background(topic, value, key):
    try:
        await producer.send_and_wait(topic, value=value, key=key)  # type: ignore[union-attr]
    except Exception as e:
        logger.error("Failed to publish event to %s: %s", topic, e)


async def publish_event(topic: str, value: dict, key: Optional[str] = None):
    global producer
    if not producer:
        logger.warning("Kafka producer not available — dropping event to %s", topic)
        return
    payload = serialize(topic, value)
    encoded_key = key.encode("utf-8") if key else None
    asyncio.create_task(_send_background(topic, payload, encoded_key))


async def _send_and_stop(topic: str, value: bytes, key: Optional[bytes] = None):
    """Create a temporary producer, send one message, and stop."""
    kwargs = {
        "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "security_protocol": settings.KAFKA_SECURITY_PROTOCOL,
    }
    if settings.KAFKA_SASL_USERNAME:
        kwargs["sasl_mechanism"] = settings.KAFKA_SASL_MECHANISM
        kwargs["sasl_plain_username"] = settings.KAFKA_SASL_USERNAME
        kwargs["sasl_plain_password"] = settings.KAFKA_SASL_PASSWORD
    if settings.KAFKA_SSL_CA_PATH:
        kwargs["ssl_context"] = _make_sni_context(
            settings.KAFKA_BOOTSTRAP_SERVERS, settings.KAFKA_SSL_CA_PATH,
        )
    try:
        p = AIOKafkaProducer(**kwargs)
        await p.start()
        await p.send_and_wait(topic, value=value, key=key)
        await p.stop()
    except Exception as e:
        logger.error("Failed to publish raw event to %s: %s", topic, e)


async def publish_raw(topic: str, value: bytes, key: Optional[bytes] = None):
    global producer
    if producer:
        asyncio.create_task(_send_background(topic, value, key))
    else:
        asyncio.create_task(_send_and_stop(topic, value, key))
