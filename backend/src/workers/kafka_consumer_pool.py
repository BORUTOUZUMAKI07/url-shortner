import asyncio

from aiokafka import AIOKafkaConsumer

from src.log_utils import get_logger

logger = get_logger(__name__)


class KafkaConnectionPool:
    def __init__(self, bootstrap_servers, **consumer_config):
        self.bootstrap_servers = bootstrap_servers
        self.consumer_config = consumer_config
        self._connection_lock = asyncio.Lock()
        self._backoff_factor = 1.0
        self._max_backoff = 30.0
        self._current_backoff = 1.0

    async def create_consumer(self, *topics) -> AIOKafkaConsumer:
        async with self._connection_lock:
            try:
                consumer = AIOKafkaConsumer(
                    *topics,
                    bootstrap_servers=self.bootstrap_servers,
                    **self.consumer_config
                )
                await consumer.start()
                logger.info("Kafka connection established")
                self._current_backoff = 1.0
                return consumer
            except Exception as e:
                logger.error("Kafka connection failed: %s", str(e))
                self._current_backoff = min(self._current_backoff * self._backoff_factor, self._max_backoff)
                await asyncio.sleep(self._current_backoff)
                raise

    async def safe_consume(self, topics, callback, auto_commit=False):
        consumer = None
        while True:
            try:
                consumer = await self.create_consumer(*topics)
                logger.info("Kafka consumer connected, consuming from %s", topics)
            except Exception as e:
                logger.error("Failed to create consumer for %s (will retry): %s", topics, str(e))
                await asyncio.sleep(self._current_backoff)
                continue

            try:
                while True:
                    try:
                        msg = await consumer.getone()
                    except asyncio.CancelledError:
                        logger.info("Fetch cancelled (rebalance), yielding for rebalance...")
                        await asyncio.sleep(1)
                        continue
                    try:
                        await callback(msg, consumer)
                        if auto_commit:
                            await consumer.commit()
                    except Exception as cb_e:
                        logger.exception("Callback error: %s", str(cb_e))
            except Exception as conn_e:
                logger.error("Consumer error for %s (will reconnect): %s", topics, str(conn_e))
            finally:
                if consumer:
                    try:
                        await consumer.stop()
                    except Exception:
                        pass
                await asyncio.sleep(self._current_backoff)
