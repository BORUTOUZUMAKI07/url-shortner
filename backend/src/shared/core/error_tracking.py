"""Sentry error tracking — opt-in via ``SENTRY_DSN``.

Deliberately separate from the OpenTelemetry pipeline. OTel ships logs, traces
and metrics to New Relic; what Sentry adds is *error grouping* — one issue per
distinct stack trace, with a release, breadcrumbs and a fix suggestion. Two
different questions: "what happened on this request" (OTel) vs "is this the
same known bug, and how many users hit it" (Sentry).

Safety rules enforced here:

* no DSN configured (the default) = **not initialised** — tests and local dev
  never ship exceptions to a third party;
* ``ENVIRONMENT=test`` never initialises, even with a DSN (a third-party SDK
  must not be a test dependency);
* ``send_default_pii=False`` and ``max_request_body_size="never"`` so bodies
  and headers never leave the box;
* the same redaction used for logs runs over the event before it is sent.

Tracing is off by default (``SENTRY_TRACES_SAMPLE_RATE=0``): traces already
flow through OTel, and enabling both would double-collect spans.
"""

from src.shared import get_logger
from src.shared.core.config import settings

logger = get_logger(__name__)

_sentry_initialized = False


def init_sentry() -> bool:
    """Initialise Sentry. Returns True when an active DSN was configured.

    Never raises: a telemetry SDK failing must not take the process down.
    """
    global _sentry_initialized
    if _sentry_initialized:
        return True
    if settings.ENVIRONMENT == "test":
        return False
    if not settings.SENTRY_DSN:
        return False
    try:
        import sentry_sdk
    except ImportError:
        logger.warning(
            "SENTRY_DSN is set but sentry-sdk is not installed; error tracking disabled"
        )
        return False

    from src.shared.core.redaction import redact_value

    def _before_send(event, hint):
        """Keep payload redaction identical to the log stream's."""
        if not settings.PII_REDACTION_ENABLED:
            return event
        try:
            return redact_value(event)
        except Exception as e:  # noqa: BLE001 - never drop an event over scrubbing
            logger.warning("Sentry before_send redaction failed: %s", e)
            return event

    try:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            send_default_pii=False,
            max_request_body_size="never",
            before_send=_before_send,
        )
        _sentry_initialized = True
        logger.info(
            "Sentry error tracking initialised (traces_sample_rate=%s)",
            settings.SENTRY_TRACES_SAMPLE_RATE,
        )
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("Sentry init failed: %s", e)
        return False


__all__ = ["init_sentry"]
