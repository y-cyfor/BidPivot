"""Generation lock and cooperative cancellation helpers."""

import logging

from app.services.progress import get_redis

logger = logging.getLogger(__name__)

CANCEL_PREFIX = "generation_cancel:"
LOCK_PREFIX = "generation_lock:"
CANCEL_TTL = 24 * 60 * 60
LOCK_TTL = 60 * 60


class GenerationCancelled(Exception):
    """Raised inside the graph when the user cancels a generation task."""


async def is_generation_cancelled(task_id: str) -> bool:
    try:
        redis = await get_redis()
        return bool(await redis.exists(f"{CANCEL_PREFIX}{task_id}"))
    except Exception:
        logger.warning("Failed to read cancellation flag for %s", task_id, exc_info=True)
        return False


async def request_generation_cancel(task_id: str) -> None:
    redis = await get_redis()
    await redis.set(f"{CANCEL_PREFIX}{task_id}", "1", ex=CANCEL_TTL)


async def clear_generation_cancel(task_id: str) -> None:
    try:
        redis = await get_redis()
        await redis.delete(f"{CANCEL_PREFIX}{task_id}")
    except Exception:
        logger.warning("Failed to clear cancellation flag for %s", task_id, exc_info=True)


async def acquire_generation_lock(project_id: str, task_id: str) -> bool:
    redis = await get_redis()
    return bool(await redis.set(f"{LOCK_PREFIX}{project_id}", task_id, nx=True, ex=LOCK_TTL))


async def release_generation_lock(project_id: str) -> None:
    try:
        redis = await get_redis()
        await redis.delete(f"{LOCK_PREFIX}{project_id}")
    except Exception:
        logger.warning("Failed to release generation lock for %s", project_id, exc_info=True)
