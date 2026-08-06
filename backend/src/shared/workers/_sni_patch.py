import logging
import ssl
from typing import Optional


def _extract_hostname(bootstrap_servers: str) -> Optional[str]:
    hostname = bootstrap_servers.split(":")[0]
    return hostname if hostname else None


def _make_sni_context(bootstrap_servers: str, cafile: str) -> ssl.SSLContext:
    """Build an SSL context for Aiven Kafka.

    Uses ``ssl.create_default_context()`` (``PROTOCOL_TLS_CLIENT`` +
    ``CERT_REQUIRED``).  Disables hostname verification because
    aiokafka connects to individual brokers by IP.  Injects the
    bootstrap hostname into ``wrap_socket`` when aiokafka connects
    to a broker by IP without ``server_hostname`` — Aiven brokers
    require a valid ``server_hostname`` to complete the TLS handshake.
    """
    sni_hostname = _extract_hostname(bootstrap_servers)
    ctx = ssl.create_default_context(cafile=cafile)
    ctx.check_hostname = False

    # Patch wrap_socket (used by direct calls)
    _orig_wrap_socket = ctx.wrap_socket
    def _wrap_socket(sock, server_side=False, do_handshake_on_connect=True,
                     suppress_ragged_eofs=True, server_hostname=None, session=None):
        return _orig_wrap_socket(sock, server_side, do_handshake_on_connect,
                                 suppress_ragged_eofs, sni_hostname, session)
    ctx.wrap_socket = _wrap_socket  # type: ignore[method-assign]

    # Patch wrap_bio (used by asyncio on Python 3.13+ / ProactorEventLoop)
    _orig_wrap_bio = ctx.wrap_bio
    def _wrap_bio(incoming, outgoing, server_side=False,
                  server_hostname=None, session=None):
        return _orig_wrap_bio(incoming, outgoing, server_side,
                              sni_hostname, session)
    ctx.wrap_bio = _wrap_bio  # type: ignore[method-assign]

    return ctx


# ---------------------------------------------------------------------------
# Backward-compatible no-op.
# ---------------------------------------------------------------------------
_PATCHED = False


def apply_sni_patch(bootstrap_hostname: Optional[str] = None) -> None:
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True
    log = logging.getLogger(__name__)
    log.info("SNI patch is not required for this Aiven cluster.")
    return
