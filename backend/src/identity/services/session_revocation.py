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

from src.shared.core.config import settings
from src.shared.core.redis import redis_client

logger = logging.getLogger("url-shortener")

_REFRESH_REVOKED_PREFIX = "refresh:revoked:"


def _revocation_ttl() -> int:
    return settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600


async def is_family_revoked(user_id: int) -> bool:
    """True when every refresh token for *user_id* has been killed.

    A Redis outage here is treated as "not revoked" so that a cache-layer
    failure cannot lock every user out; the alternative (fail closed) turns a
    cache blip into a platform-wide logout.
    """
    try:
        return bool(await redis_client.get(f"{_REFRESH_REVOKED_PREFIX}{user_id}"))
    except Exception as e:
        logger.warning("Failed to read refresh-family revocation for user %s: %s", user_id, e)
        return False


async def revoke_refresh_family(user_id: int) -> None:
    """Kill every refresh token for a user (replay detected, password changed).

    Best-effort: if Redis is down the tokens stay valid, so callers must not
    treat a failure here as "sessions are gone".
    """
    try:
        await redis_client.setex(
            f"{_REFRESH_REVOKED_PREFIX}{user_id}", _revocation_ttl(), "1"
        )
    except Exception as e:
        logger.warning("Failed to revoke refresh family for user %s: %s", user_id, e)
