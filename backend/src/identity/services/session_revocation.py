"""Refresh-family revocation, shared by every password-mutating code path.

Lives outside ``AuthService`` because ``ProfileService`` needs it too and must
not import the auth service just to reach a private method.

Setting ``refresh:revoked:{user_id}`` makes every outstanding refresh token for
that user fail on the next rotation, without needing to enumerate the individual
``refresh:session:{sid}`` records. Access tokens are untouched and expire on
their own short timer; the TTL below is only an upper bound on how long the
revocation marker needs to outlive the longest-lived refresh token.
"""

import logging
import time

from src.shared.core.config import settings
from src.shared.core.redis import redis_client

logger = logging.getLogger("url-shortener")

_REFRESH_REVOKED_PREFIX = "refresh:revoked:"


def _revocation_ttl() -> int:
    return settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600


async def is_family_revoked(user_id: int, issued_at: float | None = None) -> bool:
    """True when a refresh token for *user_id* predates the family revocation.

    The stored value is the instant of revocation, not a boolean. A token
    issued **after** that instant belongs to a fresh sign-in and must still
    work; a token issued before it was killed by the password change/replay and
    must not be revived by that fresh sign-in.

    Older deployments wrote "1". Treat any non-numeric legacy value as "every
    token is revoked" for the remainder of its TTL — conservative, and it ages
    out within one refresh-token lifetime. A token with no `iat` cannot prove it
    is newer, so it is also treated as revoked.

    A Redis outage here is treated as "not revoked" so that a cache-layer
    failure cannot lock every user out; the alternative (fail closed) turns a
    cache blip into a platform-wide logout.
    """
    try:
        raw = await redis_client.get(f"{_REFRESH_REVOKED_PREFIX}{user_id}")
    except Exception as e:
        logger.warning("Failed to read refresh-family revocation for user %s: %s", user_id, e)
        return False

    if not raw:
        return False
    # Legacy deployments wrote the boolean "1"; that is not a timestamp and
    # cannot be compared against an issued-at.
    if str(raw) == "1":
        return True
    try:
        revoked_before = float(raw)
    except (TypeError, ValueError):
        return True
    if issued_at is None:
        return True
    return float(issued_at) < revoked_before


async def revoke_refresh_family(user_id: int) -> None:
    """Kill every refresh token issued before now (replay, password change).

    Best-effort: if Redis is down the tokens stay valid, so callers must not
    treat a failure here as "sessions are gone".
    """
    try:
        await redis_client.setex(
            f"{_REFRESH_REVOKED_PREFIX}{user_id}",
            _revocation_ttl(),
            str(time.time()),
        )
    except Exception as e:
        logger.warning("Failed to revoke refresh family for user %s: %s", user_id, e)


async def upgrade_legacy_revocation_marker(user_id: int) -> None:
    """Convert a pre-timestamp ``"1"`` marker into a revocation instant.

    Older deployments had no timestamp, so a surviving boolean marker would
    otherwise reject **new** logins too for the rest of its TTL. On a
    successful sign-in we replace it with ``now``: every token issued before
    that instant stays dead, and the token we are about to mint is newer than
    it. This is not a "clear" — it re-arms the marker rather than deleting it.

    Best-effort and only writes when the marker exists; a normal login with no
    revocation does no extra Redis write.
    """
    key = f"{_REFRESH_REVOKED_PREFIX}{user_id}"
    try:
        raw = await redis_client.get(key)
        if not raw:
            return
        if str(raw) != "1":
            try:
                float(raw)
                return
            except (TypeError, ValueError):
                pass
        await redis_client.setex(key, _revocation_ttl(), str(time.time()))
    except Exception as e:
        logger.warning(
            "Failed to upgrade legacy refresh revocation for user %s: %s", user_id, e
        )
