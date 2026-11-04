import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.project import (
    ProjectCreate,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
    ProjectUpdatePublic,
)
from app.schemas.document import DocumentUpdate
from app.services import admin as admin_service
from app.services import project as project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ApiResponse[ProjectResponse])
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = await project_service.create_project(db, user.id, body)
    return {"code": 200, "data": ProjectResponse.model_validate(project), "message": "创建成功"}


@router.get("", response_model=ApiResponse[ProjectListResponse])
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = await project_service.list_projects(db, user.id, skip, limit)
    return {
        "code": 200,
        "data": ProjectListResponse(
            items=[ProjectResponse.model_validate(i) for i in items],
            total=total,
        ),
        "message": "ok",
    }


@router.get("/{project_id}", response_model=ApiResponse[ProjectDetailResponse])
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = await project_service.get_project(db, project_id, user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    return {"code": 200, "data": ProjectDetailResponse.model_validate(project), "message": "ok"}


@router.put("/{project_id}", response_model=ApiResponse[ProjectDetailResponse])
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdatePublic,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = await project_service.get_project(db, project_id, user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    updated = await project_service.update_project(db, project, ProjectUpdate(**body.model_dump(exclude_unset=True)))
    return {"code": 200, "data": ProjectDetailResponse.model_validate(updated), "message": "更新成功"}


@router.delete("/{project_id}", response_model=ApiResponse[None])
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = await project_service.get_project(db, project_id, user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    await project_service.delete_project(db, project)
    await admin_service.create_audit_log(
        db, user.id, "delete_project", "project", str(project_id), {"title": project.title}
    )
    return {"code": 200, "data": None, "message": "删除成功"}


@router.put("/{project_id}/document", response_model=ApiResponse[ProjectDetailResponse])
async def save_document(
    project_id: uuid.UUID,
    body: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = await project_service.get_project(db, project_id, user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    updated = await project_service.update_project(
        db, project, ProjectUpdate(content_html=body.content_html, content_json=body.content_json)
    )
    return {"code": 200, "data": ProjectDetailResponse.model_validate(updated), "message": "保存成功"}
