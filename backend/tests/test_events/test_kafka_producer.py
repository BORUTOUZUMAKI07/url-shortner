import asyncio
from contextlib import ExitStack
from typing import Awaitable, Iterable, List, Union
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.shared.events.kafka import publish_event, publish_raw


async def _run_publish(patches: Iterable[Mock], coro: Awaitable[None]) -> None:
    """Run a publish call and await any fire-and-forget tasks it spawns.

    ``publish_event``/``publish_raw`` schedule ``_send_background`` (and
    occasionally ``_send_and_stop``) via ``asyncio.create_task``. If those
    tasks are left pending when pytest-asyncio closes the function-scoped
    event loop, the loop reports ``RuntimeError: Event loop is closed``.
    Capturing and gathering them keeps the tests deterministic.
    """
    tasks: List[asyncio.Task] = []
    original_create_task = asyncio.create_task

    def capture(coro_obj, *args, **kwargs):
        task = original_create_task(coro_obj, *args, **kwargs)
        tasks.append(task)
        return task

    with patch("asyncio.create_task", side_effect=capture), ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        await coro
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


class TestKafkaProducer:
    @pytest.mark.asyncio
    async def test_publish_event_calls_serialize_and_send(self):
        mock_producer = AsyncMock()

        await _run_publish(
            [
                patch("src.shared.events.kafka.producer", mock_producer),
                patch("src.shared.events.kafka.serialize", return_value=b"serialized-avro-bytes"),
            ],
            publish_event("url-created", {"short_code": "test"}),
        )

        mock_producer.send_and_wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_event_with_key(self):
        mock_producer = AsyncMock()

        await _run_publish(
            [
                patch("src.shared.events.kafka.producer", mock_producer),
                patch("src.shared.events.kafka.serialize", return_value=b"serialized-avro-bytes"),
            ],
            publish_event("url-created", {"short_code": "test"}, key="test-key"),
        )

        mock_producer.send_and_wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_raw_sends_bytes(self):
        mock_producer = AsyncMock()

        await _run_publish(
            [patch("src.shared.events.kafka.producer", mock_producer)],
            publish_raw("dlq-url-clicked", b"raw-bytes"),
        )

        mock_producer.send_and_wait.assert_called_once_with(
            "dlq-url-clicked", value=b"raw-bytes", key=None
        )

    @pytest.mark.asyncio
    async def test_publish_event_no_producer_returns_gracefully(self):
        with patch("src.shared.events.kafka.producer", None):
            result = await publish_event("url-created", {"short_code": "test"})
            assert result is None

    @pytest.mark.asyncio
    async def test_publish_raw_no_producer_returns_gracefully(self):
        send_and_stop = AsyncMock()

        await _run_publish(
            [
                patch("src.shared.events.kafka.producer", None),
                patch("src.shared.events.kafka._send_and_stop", send_and_stop),
            ],
            publish_raw("some-topic", b"data"),
        )

        assert send_and_stop.await_count == 1

    @pytest.mark.asyncio
    async def test_publish_event_producer_fails_gracefully(self):
        mock_producer = AsyncMock()
        mock_producer.send_and_wait.side_effect = RuntimeError("Kafka unreachable")

        await _run_publish(
            [
                patch("src.shared.events.kafka.producer", mock_producer),
                patch("src.shared.events.kafka.serialize", return_value=b"bytes"),
                patch("src.shared.events.kafka._SEND_RETRY_DELAYS", [0, 0]),
                patch("src.shared.events.kafka.publish_raw", AsyncMock()),
            ],
            publish_event("url-created", {"short_code": "test"}),
        )

    @pytest.mark.asyncio
    async def test_publish_raw_producer_fails_gracefully(self):
        mock_producer = AsyncMock()
        mock_producer.send_and_wait.side_effect = RuntimeError("Kafka unreachable")

        await _run_publish(
            [patch("src.shared.events.kafka.producer", mock_producer)],
            publish_raw("some-topic", b"data"),
        )

    @pytest.mark.asyncio
    async def test_durable_topic_event_is_dlq_after_failed_sends(self):
        mock_producer = AsyncMock()
        mock_producer.send_and_wait.side_effect = RuntimeError("Kafka unreachable")
        dlq_publish = AsyncMock()

        await _run_publish(
            [
                patch("src.shared.events.kafka.producer", mock_producer),
                patch("src.shared.events.kafka.serialize", return_value=b"bytes"),
                patch("src.shared.events.kafka._SEND_RETRY_DELAYS", [0, 0]),
                patch("src.shared.events.kafka.publish_raw", dlq_publish),
            ],
            publish_event("url-created", {"short_code": "test"}),
        )

        # Initial attempt + 1 retry (the patched [0, 0] schedule), then the
        # payload is copied to the DLQ topic so the replay worker can
        # re-publish it once Kafka recovers.
        assert mock_producer.send_and_wait.await_count == 2
        dlq_publish.assert_awaited_once_with("dlq-url-created", b"bytes", None)

    @pytest.mark.asyncio
    async def test_durable_topic_dlq_preserves_key(self):
        mock_producer = AsyncMock()
        mock_producer.send_and_wait.side_effect = RuntimeError("Kafka unreachable")
        dlq_publish = AsyncMock()

        await _run_publish(
            [
                patch("src.shared.events.kafka.producer", mock_producer),
                patch("src.shared.events.kafka.serialize", return_value=b"bytes"),
                patch("src.shared.events.kafka._SEND_RETRY_DELAYS", [0, 0]),
                patch("src.shared.events.kafka.publish_raw", dlq_publish),
            ],
            publish_event("url-created", {"short_code": "test"}, key="abc123"),
        )

        dlq_publish.assert_awaited_once_with("dlq-url-created", b"bytes", b"abc123")

    @pytest.mark.asyncio
    async def test_best_effort_topic_is_dropped_not_dlq(self):
        mock_producer = AsyncMock()
        mock_producer.send_and_wait.side_effect = RuntimeError("Kafka unreachable")
        dlq_publish = AsyncMock()

        await _run_publish(
            [
                patch("src.shared.events.kafka.producer", mock_producer),
                patch("src.shared.events.kafka.serialize", return_value=b"bytes"),
                patch("src.shared.events.kafka._SEND_RETRY_DELAYS", [0, 0]),
                patch("src.shared.events.kafka.publish_raw", dlq_publish),
            ],
            publish_event("url-clicked", {"short_code": "test"}),
        )

        dlq_publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_successful_send_does_not_dlq(self):
        mock_producer = AsyncMock()
        dlq_publish = AsyncMock()

        await _run_publish(
            [
                patch("src.shared.events.kafka.producer", mock_producer),
                patch("src.shared.events.kafka.serialize", return_value=b"bytes"),
                patch("src.shared.events.kafka._SEND_RETRY_DELAYS", [0, 0]),
                patch("src.shared.events.kafka.publish_raw", dlq_publish),
            ],
            publish_event("url-created", {"short_code": "test"}, key="k"),
        )

        mock_producer.send_and_wait.assert_awaited_once()
        dlq_publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_retry_succeeds_without_dlq(self):
        mock_producer = AsyncMock()
        mock_producer.send_and_wait.side_effect = [RuntimeError("flaky blip"), None]
        dlq_publish = AsyncMock()

        await _run_publish(
            [
                patch("src.shared.events.kafka.producer", mock_producer),
                patch("src.shared.events.kafka.serialize", return_value=b"bytes"),
                patch("src.shared.events.kafka._SEND_RETRY_DELAYS", [0, 0]),
                patch("src.shared.events.kafka.publish_raw", dlq_publish),
            ],
            publish_event("url-created", {"short_code": "test"}),
        )

        assert mock_producer.send_and_wait.await_count == 2
        dlq_publish.assert_not_awaited()
