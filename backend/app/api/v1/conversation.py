import difflib
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.common import ApiResponse
from app.api.deps import get_current_user
from app.database import async_session, get_db
from app.models.project import Project
from app.models.user import User
from app.models.version import DocumentVersion
from app.schemas.version import ConversationRequest
from app.services.project import get_project

router = APIRouter(prefix="/bid", tags=["conversation"])


@router.post("/{project_id}/conversation")
async def conversation_modify(
    project_id: uuid.UUID,
    body: ConversationRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Conversational document modification with SSE streaming."""
    project = await get_project(db, project_id, user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    from app.services.conversation import stream_conversation_modification

    history = project.conversation_history or []

    async def event_stream():
        yield f"data: {json.dumps({'type': 'thinking', 'content': '正在分析修改指令...'})}\n\n"

        modified_html = ""
        try:
            async for kind, payload in stream_conversation_modification(
                instruction=body.instruction,
                current_html=body.current_html,
                selected_text=body.selected_text,
                conversation_history=history,
            ):
                if kind == "token":
                    modified_html += payload
                    yield f"data: {json.dumps({'type': 'token', 'content': payload})}\n\n"
                else:
                    modified_html = payload
                    yield f"data: {json.dumps({'type': 'content', 'content': modified_html})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
            return

        async with async_session() as save_db:
            # Lock the project row so concurrent edits cannot allocate the same
            # version number.
            proj_result = await save_db.execute(
                select(Project).where(Project.id == project_id).with_for_update()
            )
            proj = proj_result.scalar_one_or_none()
            if proj is None:
                yield f"data: {json.dumps({'type': 'error', 'content': '项目不存在'})}\n\n"
                return

            max_result = await save_db.execute(
                select(func.max(DocumentVersion.version_number)).where(
                    DocumentVersion.project_id == project_id
                )
            )
            version_num = (max_result.scalar() or 0) + 1

            save_db.add(DocumentVersion(
                project_id=project_id,
                version_number=version_num,
                content_html=modified_html,
                content_json=None,
                created_by="agent",
                instruction=body.instruction,
            ))

            new_history = history + [
                {"role": "user", "content": body.instruction, "timestamp": datetime.now(timezone.utc).isoformat()},
                {"role": "assistant", "content": "已完成修改", "timestamp": datetime.now(timezone.utc).isoformat()},
            ]
            proj.content_html = modified_html
            proj.conversation_history = new_history[-50:]
            await save_db.commit()

        yield f"data: {json.dumps({'type': 'complete'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{project_id}/versions/diff")
async def diff_versions(
    project_id: uuid.UUID,
    from_id: uuid.UUID,
    to_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = await get_project(db, project_id, user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    rows = (await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.project_id == project_id,
            DocumentVersion.id.in_([from_id, to_id]),
        )
    )).scalars().all()
    by_id = {str(version.id): version for version in rows}
    source = by_id.get(str(from_id))
    target = by_id.get(str(to_id))
    if source is None or target is None:
        raise HTTPException(status_code=404, detail="版本不存在")

    diff = list(difflib.unified_diff(
        (source.content_html or "").splitlines(),
        (target.content_html or "").splitlines(),
        fromfile=f"v{source.version_number}",
        tofile=f"v{target.version_number}",
        lineterm="",
    ))
    return {"code": 200, "data": {"diff": "\n".join(diff)}, "message": "ok"}


@router.post("/{project_id}/versions/{version_id}/restore", response_model=ApiResponse[object])
async def restore_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = await get_project(db, project_id, user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    version = (await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.project_id == project_id,
        )
    )).scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="版本不存在")

    max_result = await db.execute(
        select(func.max(DocumentVersion.version_number)).where(DocumentVersion.project_id == project_id)
    )
    new_number = (max_result.scalar() or 0) + 1
    db.add(DocumentVersion(
        project_id=project_id,
        version_number=new_number,
        content_html=version.content_html,
        content_json=version.content_json,
        created_by="restore",
        instruction=f"恢复到版本 v{version.version_number}",
    ))
    project.content_html = version.content_html
    await db.commit()
    return {"code": 200, "data": {"version_number": new_number}, "message": "已恢复该版本"}


@router.get("/{project_id}/versions")
async def list_versions(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all versions of a project document."""
    from app.schemas.version import VersionListResponse, VersionResponse

    project = await get_project(db, project_id, user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.project_id == project_id)
        .order_by(DocumentVersion.version_number.desc())
    )
    versions = result.scalars().all()
    return {
        "code": 200,
        "data": VersionListResponse(
            items=[VersionResponse.model_validate(v) for v in versions],
            total=len(versions),
        ),
        "message": "ok",
    }
