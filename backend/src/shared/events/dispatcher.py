from abc import ABC, abstractmethod
from typing import Optional

from src.shared import get_logger

logger = get_logger(__name__)


class EventDispatcher(ABC):
    @abstractmethod
    async def dispatch(self, topic: str, value: dict, key: Optional[str] = None) -> None:
        ...


class KafkaEventDispatcher(EventDispatcher):
    async def dispatch(self, topic: str, value: dict, key: Optional[str] = None) -> None:
        from src.shared.events.kafka import publish_event
        try:
            await publish_event(topic, value, key=key)
        except Exception as e:
            logger.error("Failed to dispatch event to %s: %s", topic, e)


class NullEventDispatcher(EventDispatcher):
    async def dispatch(self, topic: str, value: dict, key: Optional[str] = None) -> None:
        pass
