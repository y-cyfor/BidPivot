import json
from datetime import datetime, timezone

import redis.asyncio as aioredis

from app.config import settings

_redis = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def close_redis() -> None:
    """Close the process-wide Redis client.

    Celery tasks create a fresh event loop per invocation; a client created on
    the previous loop must be released before that loop is closed.
    """
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def publish_event(task_id: str, event: dict) -> None:
    """Publish a progress event to Redis channel for WebSocket broadcast."""
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    r = await get_redis()
    await r.publish(f"generation:{task_id}", json.dumps(event))


async def publish_section_status(task_id: str, section_id: str, status: str) -> None:
    await publish_event(task_id, {
        "type": "section_status",
        "section_id": section_id,
        "status": status,
    })


async def publish_thinking(task_id: str, section_id: str, agent: str, content: str) -> None:
    await publish_event(task_id, {
        "type": "thinking",
        "section_id": section_id,
        "agent": agent,
        "content": content,
    })


async def publish_tool_call(task_id: str, section_id: str, tool: str, args: dict, result_summary: str) -> None:
    await publish_event(task_id, {
        "type": "tool_call",
        "section_id": section_id,
        "tool": tool,
        "args": args,
        "result_summary": result_summary,
    })


async def publish_content_token(task_id: str, section_id: str, token: str) -> None:
    await publish_event(task_id, {
        "type": "content_token",
        "section_id": section_id,
        "token": token,
    })


async def publish_locked_var(task_id: str, var_name: str, value: str, source: str) -> None:
    await publish_event(task_id, {
        "type": "locked_var",
        "var_name": var_name,
        "value": value,
        "source": source,
    })


async def publish_batch_done(task_id: str, batch: int, completed: list[str]) -> None:
    await publish_event(task_id, {
        "type": "batch_done",
        "batch": batch,
        "completed": completed,
    })


async def publish_generation_complete(task_id: str, total_sections: int, failed_sections: list[str] | None = None) -> None:
    failed_sections = failed_sections or []
    await publish_event(task_id, {
        "type": "generation_complete",
        "total_sections": total_sections,
        "failed_sections": failed_sections,
        "partial": bool(failed_sections),
    })


async def publish_generation_failed(task_id: str, message: str) -> None:
    await publish_event(task_id, {
        "type": "generation_failed",
        "message": message,
    })


async def publish_generation_cancelled(task_id: str) -> None:
    await publish_event(task_id, {
        "type": "generation_cancelled",
    })


async def publish_error(task_id: str, section_id: str, message: str) -> None:
    await publish_event(task_id, {
        "type": "error",
        "section_id": section_id,
        "message": message,
    })
