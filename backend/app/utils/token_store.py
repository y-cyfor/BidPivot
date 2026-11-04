"""Short-lived JWT revocation list backed by Redis."""

import logging
import time

from app.services.progress import get_redis

logger = logging.getLogger(__name__)

REVOKED_PREFIX = "jwt_revoked:"


async def revoke_token(jti: str | None, expires_at: int | float | None) -> None:
    if not jti:
        return
    ttl = 1
    if expires_at:
        ttl = max(1, int(expires_at - time.time()))
    try:
        redis = await get_redis()
        await redis.set(f"{REVOKED_PREFIX}{jti}", "1", ex=ttl)
    except Exception:
        logger.warning("Failed to add token %s to the revocation list", jti, exc_info=True)


async def is_token_revoked(jti: str | None) -> bool:
    if not jti:
        return False
    try:
        redis = await get_redis()
        return bool(await redis.exists(f"{REVOKED_PREFIX}{jti}"))
    except Exception:
        # Redis outage must not take authentication down; tokens then remain
        # valid until their natural expiry.
        logger.warning("Failed to check token revocation for %s", jti, exc_info=True)
        return False
