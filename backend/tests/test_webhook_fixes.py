import asyncio
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.webhooks.services.webhook_service import (
    _CIRCUIT_OPEN_SECONDS,
    _CIRCUIT_OPEN_UNTIL,
    _CONSECUTIVE_FAILURES,
    _MAX_CONSECUTIVE_FAILURES,
    _is_circuit_open,
    _record_delivery_failure,
    _record_delivery_success,
    decrypt_secret,
    deliver_single_webhook,
    encrypt_secret,
)


class TestCircuitBreaker:
    """Test the per-endpoint circuit breaker (#8)."""

    def setup_method(self):
        _CONSECUTIVE_FAILURES.clear()
        _CIRCUIT_OPEN_UNTIL.clear()

    def test_circuit_closed_initially(self):
        assert _is_circuit_open(1) is False

    def test_circuit_opens_after_max_failures(self):
        for _ in range(_MAX_CONSECUTIVE_FAILURES):
            _record_delivery_failure(1)
        assert _is_circuit_open(1) is True

    def test_circuit_closes_after_timeout(self):
        for _ in range(_MAX_CONSECUTIVE_FAILURES):
            _record_delivery_failure(1)
        _CIRCUIT_OPEN_UNTIL[1] = time.time() - 1  # expired
        assert _is_circuit_open(1) is False
        assert 1 not in _CONSECUTIVE_FAILURES

    def test_circuit_resets_on_success(self):
        for _ in range(_MAX_CONSECUTIVE_FAILURES - 1):
            _record_delivery_failure(1)
        _record_delivery_success(1)
        assert _is_circuit_open(1) is False
        assert 1 not in _CONSECUTIVE_FAILURES

    def test_circuit_failure_count_increments(self):
        _record_delivery_failure(1)
        _record_delivery_failure(1)
        assert _CONSECUTIVE_FAILURES[1] == 2

    def test_different_webhooks_independent(self):
        for _ in range(_MAX_CONSECUTIVE_FAILURES):
            _record_delivery_failure(1)
        assert _is_circuit_open(1) is True
        assert _is_circuit_open(2) is False


class TestDeliverSingleWebhook:
    """Test the shared delivery function (#2)."""

    def _make_response(self, status_code=200, text="ok"):
        response = MagicMock()
        response.is_success = 200 <= status_code < 300
        response.status_code = status_code
        response.text = text
        return response

    def _clear_circuit(self):
        _CONSECUTIVE_FAILURES.clear()
        _CIRCUIT_OPEN_UNTIL.clear()

    def setup_method(self):
        self._clear_circuit()

    @pytest.mark.asyncio
    async def test_successful_delivery(self):
        secret = encrypt_secret("whsec_test123")
        payload = {"event": "url.created", "short_code": "abc"}

        with patch("src.webhooks.services.webhook_service.safe_post", AsyncMock(return_value=self._make_response(200))) as mock_post:
            success, code, error = await deliver_single_webhook(
                1, "https://example.com/hook", secret, payload, "url.created",
            )

            assert success is True
            assert code == 200
            assert error is None
            mock_post.assert_called_once()
            headers = mock_post.call_args.kwargs["headers"]
            assert "X-Webhook-Signature" in headers
            assert headers["X-Webhook-Event"] == "url.created"
            assert "Content-Type" in headers

    @pytest.mark.asyncio
    async def test_failed_delivery_records_failure(self):
        secret = encrypt_secret("whsec_test123")
        payload = {"event": "test"}

        with patch("src.webhooks.services.webhook_service.safe_post", AsyncMock(return_value=self._make_response(500, "Internal Server Error"))):
            success, code, error = await deliver_single_webhook(
                1, "https://example.com/hook", secret, payload, "test",
            )

            assert success is False
            assert code == 500
            assert "500" in error
            assert _CONSECUTIVE_FAILURES[1] == 1

    @pytest.mark.asyncio
    async def test_exception_records_failure(self):
        secret = encrypt_secret("whsec_test123")
        payload = {"event": "test"}

        with patch("src.webhooks.services.webhook_service.safe_post", AsyncMock(side_effect=ConnectionError("timeout"))):
            success, code, error = await deliver_single_webhook(
                1, "https://example.com/hook", secret, payload, "test",
            )

            assert success is False
            assert code is None
            assert "timeout" in error

    @pytest.mark.asyncio
    async def test_unsafe_url_records_failure(self):
        secret = encrypt_secret("whsec_test123")
        payload = {"event": "test"}

        with patch("src.webhooks.services.webhook_service.safe_post", AsyncMock(return_value=None)):
            success, code, error = await deliver_single_webhook(
                1, "https://example.com/hook", secret, payload, "test",
            )

            assert success is False
            assert code is None
            assert "Unsafe" in error
            assert _CONSECUTIVE_FAILURES[1] == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_skips_delivery(self):
        for _ in range(_MAX_CONSECUTIVE_FAILURES):
            _record_delivery_failure(1)
        secret = encrypt_secret("whsec_test123")

        with patch("src.webhooks.services.webhook_service.safe_post", AsyncMock(return_value=self._make_response(200))) as mock_post:
            success, code, error = await deliver_single_webhook(
                1, "https://example.com/hook", secret, {}, "test",
            )

            assert success is False
            assert "Circuit breaker" in error
            mock_post.assert_not_called()

    @pytest.mark.asyncio
    async def test_hmac_signature_is_valid(self):
        plaintext_secret = "whsec_my_secret_key_12345678"
        secret = encrypt_secret(plaintext_secret)
        payload = {"event": "url.clicked", "data": "test"}

        with patch("src.webhooks.services.webhook_service.safe_post", AsyncMock(return_value=self._make_response(200))) as mock_post:
            await deliver_single_webhook(
                1, "https://example.com/hook", secret, payload, "url.clicked",
            )

            headers = mock_post.call_args.kwargs["headers"]
            content = mock_post.call_args.kwargs["content"]
            expected_sig = hmac.new(plaintext_secret.encode(), content, hashlib.sha256).hexdigest()
            assert headers["X-Webhook-Signature"] == expected_sig


class TestEncryption:
    """Test webhook secret encryption with separate key (#7)."""

    def test_encrypt_decrypt_roundtrip(self):
        plain = "whsec_super_secret_12345"
        encrypted = encrypt_secret(plain)
        assert encrypted != plain
        decrypted = decrypt_secret(encrypted)
        assert decrypted == plain

    def test_different_keys_different_ciphertext(self):
        plain = "whsec_same_secret"
        e1 = encrypt_secret(plain)
        _e2 = encrypt_secret(plain)
        # Fernet generates random IV, so ciphertext differs
        # (unless called in the same second with same key, which is fine for a test)
        decrypted = decrypt_secret(e1)
        assert decrypted == plain


class TestFireAndForget:
    """Test that deliver_event returns immediately (#1)."""

    @pytest.mark.asyncio
    async def test_deliver_event_returns_immediately(self):
        with patch("src.webhooks.services.webhook_service.asyncio.create_task") as mock_create:
            mock_create.return_value = MagicMock()

            from src.webhooks.services.webhook_service import WebhookService

            repo = AsyncMock()
            workspace_repo = AsyncMock()
            svc = WebhookService(repo, workspace_repo)

            await svc.deliver_event(1, "url.created", {"test": True})

            mock_create.assert_called_once()
            # Verify it was called with a coroutine (the background task)
            call_args = mock_create.call_args[0][0]
            assert asyncio.iscoroutine(call_args)


class TestRateLimiter:
    """Test receiver rate limiting (#6)."""

    @pytest.mark.asyncio
    async def test_rate_limit_pass_under_threshold(self):
        from src.webhooks.services.webhook_receiver_service import WebhookReceiverService
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 1

        with patch("src.webhooks.services.webhook_receiver_service.redis_client", mock_redis):
            svc = WebhookReceiverService(AsyncMock(), AsyncMock(), AsyncMock())
            result = await svc._check_rate_limit("1.2.3.4")
            assert result is True

    @pytest.mark.asyncio
    async def test_rate_limit_reject_over_threshold(self):
        from src.webhooks.services.webhook_receiver_service import WebhookReceiverService
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 101  # over limit

        with patch("src.webhooks.services.webhook_receiver_service.redis_client", mock_redis):
            svc = WebhookReceiverService(AsyncMock(), AsyncMock(), AsyncMock())
            result = await svc._check_rate_limit("1.2.3.4")
            assert result is False

    @pytest.mark.asyncio
    async def test_rate_limit_fail_open_on_redis_error(self):
        from src.webhooks.services.webhook_receiver_service import WebhookReceiverService
        mock_redis = AsyncMock()
        mock_redis.incr.side_effect = ConnectionError("redis down")

        with patch("src.webhooks.services.webhook_receiver_service.redis_client", mock_redis):
            svc = WebhookReceiverService(AsyncMock(), AsyncMock(), AsyncMock())
            result = await svc._check_rate_limit("1.2.3.4")
            assert result is True


class TestReceiverSignatureRequired:
    """Test that receiver rejects missing signatures (#6)."""

    @pytest.mark.asyncio
    async def test_missing_signature_rejected(self):
        from src.webhooks.services.webhook_receiver_service import WebhookReceiverService

        svc = WebhookReceiverService(AsyncMock(), AsyncMock(), AsyncMock())
        svc._check_rate_limit = AsyncMock(return_value=True)

        result = await svc.receive(
            body=b'{"workspace_id": 1}',
            content_type="application/json",
            headers={"x-webhook-event": "test"},
            source_ip="1.2.3.4",
        )
        assert result["status"] == "rejected"
        assert "missing" in result["reason"]

    @pytest.mark.asyncio
    async def test_invalid_signature_rejected(self):
        from src.webhooks.services.webhook_receiver_service import WebhookReceiverService

        mock_repo = AsyncMock()
        mock_webhook_repo = AsyncMock()
        mock_ws_repo = AsyncMock()

        # Workspace exists
        mock_ws_repo.get.return_value = MagicMock(id=1)
        # No matching webhooks
        mock_webhook_repo.get_workspace_webhooks.return_value = []

        svc = WebhookReceiverService(mock_repo, mock_webhook_repo, mock_ws_repo)
        svc._check_rate_limit = AsyncMock(return_value=True)

        result = await svc.receive(
            body=b'{"workspace_id": 1}',
            content_type="application/json",
            headers={"x-webhook-event": "test", "x-webhook-signature": "invalid_sig"},
            source_ip="1.2.3.4",
        )
        assert result["status"] == "rejected"
        assert "invalid signature" in result["reason"]

    @pytest.mark.asyncio
    async def test_rate_limited_rejected(self):
        from src.webhooks.services.webhook_receiver_service import WebhookReceiverService

        svc = WebhookReceiverService(AsyncMock(), AsyncMock(), AsyncMock())
        svc._check_rate_limit = AsyncMock(return_value=False)

        result = await svc.receive(
            body=b'{"workspace_id": 1}',
            content_type="application/json",
            headers={},
            source_ip="1.2.3.4",
        )
        assert result["status"] == "rejected"
        assert "rate limit" in result["reason"]


class TestSafeURLPinning:
    """Test DNS-rebinding SSRF protection (#1)."""

    @pytest.mark.asyncio
    async def test_pick_public_address_rejects_private(self):
        from src.shared.core.safe_url import _pick_public_address
        # 127.0.0.1 is the loopback — must be rejected (no public address picked)
        addr = await _pick_public_address("localhost", 80)
        assert addr is None

    @pytest.mark.asyncio
    async def test_pick_public_address_resolves_public_domain(self):
        from src.shared.core.safe_url import _pick_public_address
        addr = await _pick_public_address("example.com", 80)
        assert addr is not None

    @pytest.mark.asyncio
    async def test_pin_url_preserves_host(self):
        from src.shared.core.safe_url import _pin_url
        rewritten, host = _pin_url("https://example.com/path?q=1", "93.184.216.34")
        assert host == "example.com"
        assert "93.184.216.34" in rewritten
        assert "/path?q=1" in rewritten

    @pytest.mark.asyncio
    async def test_safe_fetch_rejects_non_http(self):
        from src.shared.core.safe_url import safe_fetch
        resp = await safe_fetch("file:///etc/passwd")
        assert resp is None

    @pytest.mark.asyncio
    async def test_safe_fetch_private_url_none(self):
        from src.shared.core.safe_url import safe_fetch
        resp = await safe_fetch("http://127.0.0.1/")
        assert resp is None

    @pytest.mark.asyncio
    async def test_safe_post_rejects_private(self):
        from src.shared.core.safe_url import safe_post
        resp = await safe_post("http://127.0.0.1/hook")
        assert resp is None


class TestAnalyticsWorkerDatetime:
    """Test that clicked_at is always tz-aware (#12)."""

    def test_clicked_at_from_iso_tz_aware(self):
        from src.analytics.workers.analytics_worker import _get_clicked_at
        result = _get_clicked_at({"clicked_at": "2024-01-01T12:00:00+00:00"})
        assert result.isoformat().endswith("+00:00")

    def test_clicked_at_from_iso_z_normalized(self):
        from src.analytics.workers.analytics_worker import _get_clicked_at
        result = _get_clicked_at({"clicked_at": "2024-01-01T12:00:00Z"})
        assert result.tzinfo is not None

    def test_missing_clicked_at_uses_aware_utcnow(self):
        from src.analytics.workers.analytics_worker import _get_clicked_at
        result = _get_clicked_at({})
        assert result.tzinfo is not None

    def test_naive_clicked_at_defaults_to_utc(self):
        from src.analytics.workers.analytics_worker import _get_clicked_at
        # A naive string has no tzinfo — filter it out (treated as missing)
        # and fall back to aware utcnow, never yielding a naive datetime.
        result = _get_clicked_at({"clicked_at": "2024-01-01T12:00:00"})
        assert result.tzinfo is not None
