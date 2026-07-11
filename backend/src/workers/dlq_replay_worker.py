import asyncio
import ssl

from src.core.config import settings
from src.events.kafka import init_kafka, publish_raw
from src.log_utils import get_logger, setup_logging
from src.workers._sni_patch import apply_sni_patch
from src.workers.kafka_consumer_pool import KafkaConnectionPool

DLQ_TOPIC_MAP = {
    "dlq-url-created": "url-created",
    "dlq-url-clicked": "url-clicked",
}


async def handle_dlq_message(msg, consumer, logger):
    original_topic = DLQ_TOPIC_MAP.get(msg.topic)
    if not original_topic:
        logger.warning("Unknown DLQ topic: %s", msg.topic)
        await consumer.commit()
        return

    logger.info("Replaying message from %s to %s (offset=%s)", msg.topic, original_topic, msg.offset)
    try:
        await publish_raw(original_topic, msg.value, msg.key)
        logger.info("Replayed to %s successfully", original_topic)
        await consumer.commit()
    except Exception as e:
        logger.exception("Failed to replay to %s: %s", original_topic, str(e))
        await asyncio.sleep(5)


async def consume_dlq_replay():
    setup_logging()
    logger = get_logger("dlq-replay-worker")

    await init_kafka()

    kwargs = {
        "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "security_protocol": settings.KAFKA_SECURITY_PROTOCOL,
        "group_id": "dlq-replay-worker-v1",
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
        context = ssl.create_default_context(cafile=settings.KAFKA_SSL_CA_PATH)
        context.check_hostname = False
        kwargs["ssl_context"] = context

    apply_sni_patch(settings.KAFKA_BOOTSTRAP_SERVERS)

    kwargs_without_bootstrap = kwargs.copy()
    kwargs_without_bootstrap.pop("bootstrap_servers", None)
    pool = KafkaConnectionPool(settings.KAFKA_BOOTSTRAP_SERVERS, **kwargs_without_bootstrap)
    logger.info("DLQ Replay Worker listening on: dlq-url-created, dlq-url-clicked")

    await pool.safe_consume(
        topics=["dlq-url-created", "dlq-url-clicked"],
        callback=lambda msg, consumer: handle_dlq_message(msg, consumer, logger),
        auto_commit=False,
    )


if __name__ == "__main__":
    asyncio.run(consume_dlq_replay())
