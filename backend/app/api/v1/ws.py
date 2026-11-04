import json
import logging
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.common import ApiResponse
from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.project import get_project
from app.services.progress import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])
ticket_router = APIRouter(prefix="/ws", tags=["websocket"])

WS_TICKET_PREFIX = "ws_ticket:"
WS_TICKET_TTL = 120


class WsTicketRequest(BaseModel):
    task_id: str
    project_id: uuid.UUID


@ticket_router.post("/ticket", response_model=ApiResponse[object])
async def create_ws_ticket(
    body: WsTicketRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Issue a short-lived, single-use ticket for a generation WebSocket.

    The access token must not appear in the WebSocket URL (proxy/access logs).
    """
    project = await get_project(db, body.project_id, user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    ticket = secrets.token_urlsafe(32)
    payload = json.dumps({
        "user_id": str(user.id),
        "project_id": str(body.project_id),
        "task_id": body.task_id,
    })
    redis = await get_redis()
    await redis.set(f"{WS_TICKET_PREFIX}{ticket}", payload, ex=WS_TICKET_TTL)

    return {
        "code": 200,
        "data": {"ticket": ticket, "expires_in": WS_TICKET_TTL},
        "message": "ok",
    }


@router.websocket("/ws/generation/{task_id}")
async def generation_websocket(websocket: WebSocket, task_id: str):
    """Push generation progress events to the owner of the project."""
    ticket = websocket.query_params.get("ticket")
    if not ticket:
        await websocket.close(code=4001, reason="Missing ticket")
        return

    redis = await get_redis()
    raw = await redis.getdel(f"{WS_TICKET_PREFIX}{ticket}")
    if not raw:
        await websocket.close(code=4001, reason="Invalid or expired ticket")
        return

    try:
        ticket_data = json.loads(raw)
    except json.JSONDecodeError:
        await websocket.close(code=4001, reason="Invalid ticket")
        return

    if ticket_data.get("task_id") != task_id:
        await websocket.close(code=4003, reason="Ticket does not match task")
        return

    await websocket.accept()

    pubsub = redis.pubsub()
    await pubsub.subscribe(f"generation:{task_id}")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WebSocket error for task {task_id}: {e}")
    finally:
        try:
            await pubsub.unsubscribe(f"generation:{task_id}")
            await pubsub.aclose()
        except Exception:
            logger.debug("Failed to close pubsub for task %s", task_id, exc_info=True)
