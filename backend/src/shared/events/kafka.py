import asyncio
from typing import Any, Optional

from aiokafka import AIOKafkaProducer

from src.shared import get_logger
from src.shared.core.config import settings
from src.shared.core.metrics import record_kafka_message
from src.shared.events.schemas import serialize
from src.shared.workers._sni_patch import _make_sni_context

logger = get_logger(__name__)

producer: Optional[AIOKafkaProducer] = None

# Background send tasks are tracked so close_kafka() can drain in-flight
# messages before stopping the producer — otherwise fire-and-forget sends are
# silently destroyed on shutdown.
_pending_sends: set[asyncio.Task] = set()

_RETRY_DELAYS = [1, 2, 4, 8, 16]  # exponential backoff seconds

# Lifecycle events are durable: losing one means a downstream effect (metadata
# enrichment, webhooks) never happens. Click/analytics events are high-volume
# and low-value-per-event — they stay best-effort. When a durable publish keeps
# failing, its payload is copied to the corresponding DLQ topic, which the DLQ
# replay worker (dlq_replay_worker.py) re-publishes once Kafka recovers.
DURABLE_TOPIC_DLQ = {
    "url-created": "dlq-url-created",
}

# Per-send retry schedule (seconds). Small and quick: half a second to two
# seconds, three attempts, then the DLQ copy for durable topics. A broker blip
# that brief is absorbed without ever reaching the DLQ.
_SEND_RETRY_DELAYS = [0.5, 1.0, 2.0]


def _track(task: asyncio.Task) -> None:
    _pending_sends.add(task)
    task.add_done_callback(_pending_sends.discard)


async def init_kafka():
    global producer
    if producer is not None:
        logger.info("Kafka Producer already initialized.")
        return
    kwargs: dict[str, Any] = {
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
    if _pending_sends:
        sends = list(_pending_sends)
        try:
            await asyncio.wait_for(asyncio.gather(*sends, return_exceptions=True), timeout=10)
        except asyncio.TimeoutError:
            logger.warning("Timed out draining %d pending Kafka sends", len(sends))
    if producer:
        try:
            await producer.stop()
        except Exception as e:
            logger.error("Error stopping Kafka producer: %s", e)
        producer = None
        logger.info("Kafka Producer stopped.")


async def _send_background(topic, value, key):
    last_error: Exception | None = None
    for attempt, delay in enumerate(_SEND_RETRY_DELAYS):
        try:
            await producer.send_and_wait(topic, value=value, key=key)  # type: ignore[union-attr]
            record_kafka_message("produced", topic)
            return
        except Exception as e:
            last_error = e
            logger.warning(
                "Failed to publish event to %s (attempt %d/%d): %s",
                topic, attempt + 1, len(_SEND_RETRY_DELAYS), e,
            )
            if attempt < len(_SEND_RETRY_DELAYS) - 1:
                await asyncio.sleep(delay)

    dlq_topic = DURABLE_TOPIC_DLQ.get(topic)
    if dlq_topic:
        # At-least-once for lifecycle events: the replay worker re-publishes
        # this message to the original topic once the broker recovers. The DLQ
        # topic itself is best-effort here (it fails when Kafka is fully down —
        # the retry loop above already absorbed the short blips).
        try:
            await publish_raw(dlq_topic, value, key)
            logger.error("Moved event from %s to %s after %d failed attempts", topic, dlq_topic, len(_SEND_RETRY_DELAYS))
        except Exception as e:
            logger.error("Failed to move event from %s to %s: %s", topic, dlq_topic, e)
    else:
        # Best-effort topic (analytics): drop, but say so loudly.
        logger.error("Failed to publish event to %s after %d attempts: %s", topic, len(_SEND_RETRY_DELAYS), last_error)


async def publish_event(topic: str, value: dict, key: Optional[str] = None):
    global producer
    if not producer:
        logger.warning("Kafka producer not available — dropping event to %s", topic)
        return
    payload = serialize(topic, value)
    encoded_key = key.encode("utf-8") if key else None
    _track(asyncio.create_task(_send_background(topic, payload, encoded_key)))


async def _send_and_stop(topic: str, value: bytes, key: Optional[bytes] = None):
    """Create a temporary producer, send one message, and stop."""
    kwargs: dict[str, Any] = {
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
    p: AIOKafkaProducer | None = None
    try:
        p = AIOKafkaProducer(**kwargs)
        await p.start()
        await p.send_and_wait(topic, value=value, key=key)
        record_kafka_message("produced", topic)
    except Exception as e:
        logger.error("Failed to publish raw event to %s: %s", topic, e)
    finally:
        # stop() in finally so a failed send doesn't leak the producer's
        # connections (workers use this path for every DLQ publish).
        if p is not None:
            try:
                await p.stop()
            except Exception as e:
                logger.error("Error stopping temporary producer: %s", e)


async def publish_raw(topic: str, value: bytes, key: Optional[bytes] = None):
    global producer
    if producer:
        _track(asyncio.create_task(_send_background(topic, value, key)))
    else:
        _track(asyncio.create_task(_send_and_stop(topic, value, key)))
