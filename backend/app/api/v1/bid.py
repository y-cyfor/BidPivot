import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.schemas.common import ApiResponse
from app.api.deps import get_current_user
from app.celery_app import celery_app
from app.database import get_db
from app.models.project import Project
from app.models.token_usage import TokenUsage
from app.models.uploaded_file import UploadedFile
from app.models.user import User
from app.schemas.project import ProjectUpdate
from app.services import agent
from app.services.generation_control import (
    acquire_generation_lock,
    release_generation_lock,
    request_generation_cancel,
)
from app.services.progress import publish_generation_cancelled
from app.services.project import get_project, update_project
from app.services.usage import get_usage, start_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bid", tags=["bid"])


async def _get_project_files(db: AsyncSession, project_id: uuid.UUID) -> str:
    result = await db.execute(
        select(UploadedFile).where(
            UploadedFile.project_id == project_id,
            UploadedFile.parse_status == "completed",
        )
    )
    files = result.scalars().all()
    return "\n\n".join([f"【{f.original_name}】\n{f.parsed_content}" for f in files if f.parsed_content])


@router.post("/{project_id}/generate-outline", response_model=ApiResponse[object])
async def generate_outline(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = await get_project(db, project_id, user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    file_content = await _get_project_files(db, project_id)
    if not file_content:
        raise HTTPException(status_code=400, detail="请先上传招标文件")

    from app.services.agents.parser import run_parse_agent

    start_usage()
    requirements = await run_parse_agent(file_content, f"outline-{project_id}")
    outline = await agent.generate_outline(file_content, project.industry_tags, requirements)
    await update_project(
        db,
        project,
        ProjectUpdate(
            outline_json=outline,
            requirements_json=requirements,
            status="outline_firming",
        ),
    )
    usage = get_usage()
    if usage["total"] > 0:
        db.add(TokenUsage(
            user_id=user.id,
            project_id=project.id,
            session_id=f"outline-{project_id}",
            input_tokens=usage["input"],
            output_tokens=usage["output"],
            total_tokens=usage["total"],
        ))
        await db.commit()

    return {"code": 200, "data": outline, "message": "大纲生成成功"}


@router.post("/{project_id}/generate-full", response_model=ApiResponse[object])
async def generate_full(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = await get_project(db, project_id, user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    # Idempotency: a second click returns the running task instead of starting
    # a parallel generation that would race on the same project row.
    if project.status == "generating" and project.generation_task_id:
        return {
            "code": 200,
            "data": {"task_id": project.generation_task_id},
            "message": "生成任务进行中",
        }

    outline = project.outline_json or {}
    if not outline.get("sections"):
        raise HTTPException(status_code=400, detail="请先生成并确认大纲")

    task_id = str(uuid.uuid4())
    try:
        locked = await acquire_generation_lock(str(project_id), task_id)
    except Exception:
        logger.warning("Generation lock unavailable; continuing without it", exc_info=True)
        locked = True

    if not locked:
        await db.refresh(project)
        if project.status == "generating" and project.generation_task_id:
            return {
                "code": 200,
                "data": {"task_id": project.generation_task_id},
                "message": "生成任务进行中",
            }
        # A cancelled task may still hold the lock; clear it and retry once.
        await release_generation_lock(str(project_id))
        locked = await acquire_generation_lock(str(project_id), task_id)
        if not locked:
            raise HTTPException(status_code=409, detail="该项目正在生成，请稍后再试")

    file_content = await _get_project_files(db, project_id)

    project.status = "generating"
    project.generation_task_id = task_id
    await db.commit()

    from app.tasks.generation import run_generation_task
    try:
        await run_in_threadpool(
            run_generation_task.delay,
            project_id=str(project_id),
            task_id=task_id,
            file_content=file_content,
            outline=outline,
        )
    except Exception as exc:
        project.status = "failed"
        project.generation_task_id = None
        await db.commit()
        await release_generation_lock(str(project_id))
        logger.error("Failed to enqueue generation task: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail="生成任务投递失败，请检查任务队列") from exc

    return {"code": 200, "data": {"task_id": task_id}, "message": "生成任务已启动"}


@router.post("/{project_id}/cancel", response_model=ApiResponse[object])
async def cancel_generation(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = await get_project(db, project_id, user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status != "generating" or not project.generation_task_id:
        raise HTTPException(status_code=400, detail="当前没有正在执行的生成任务")

    task_id = project.generation_task_id
    try:
        await request_generation_cancel(task_id)
        await run_in_threadpool(celery_app.control.revoke, task_id, terminate=False)
    except Exception as exc:
        logger.error("Failed to cancel generation task %s: %s", task_id, exc, exc_info=True)
        raise HTTPException(status_code=503, detail="取消失败，请稍后再试") from exc

    project.status = "cancelled"
    project.generation_task_id = None
    await db.commit()
    await publish_generation_cancelled(task_id)
    return {"code": 200, "data": {"task_id": task_id}, "message": "已提交取消"}


@router.get("/{project_id}/check-report", response_model=ApiResponse[object])
async def get_check_report(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = await get_project(db, project_id, user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"code": 200, "data": project.check_report or {}, "message": "ok"}


@router.put("/{project_id}/outline", response_model=ApiResponse[object])
async def save_outline(
    project_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = await get_project(db, project_id, user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    await update_project(db, project, ProjectUpdate(outline_json=body))
    return {"code": 200, "data": body, "message": "大纲保存成功"}
