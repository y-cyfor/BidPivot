import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.common import ApiResponse
from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.admin import (
    AgentTemplateResponse,
    AgentTemplateUpdate,
    AuditLogResponse,
    ModelConfigCreate,
    ModelConfigResponse,
    ModelConfigUpdate,
    TokenStatsResponse,
    UserAdminResponse,
    UserCreateAdmin,
    UserResetPassword,
    UserUpdateAdmin,
)
from app.services import admin as admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/models/config", response_model=ApiResponse[object])
async def get_model_configs(type: str | None = Query(None), db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    configs = await admin_service.get_model_configs(db, type)
    return {"code": 200, "data": [ModelConfigResponse.model_validate(c) for c in configs], "message": "ok"}


@router.post("/models/config", response_model=ApiResponse[object])
async def create_model_config(body: ModelConfigCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    config = await admin_service.create_model_config(db, body)
    await admin_service.create_audit_log(
        db, user.id, "create_model_config", "model_config", str(config.id),
        {"type": config.type, "model": config.model_name},
    )
    return {"code": 200, "data": ModelConfigResponse.model_validate(config), "message": "创建成功"}


@router.put("/models/config/{config_id}", response_model=ApiResponse[object])
async def update_model_config(config_id: uuid.UUID, body: ModelConfigUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    config = await admin_service.update_model_config(db, config_id, body)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    await admin_service.create_audit_log(
        db, user.id, "update_model_config", "model_config", str(config.id),
        {"type": config.type, "model": config.model_name},
    )
    return {"code": 200, "data": ModelConfigResponse.model_validate(config), "message": "更新成功"}


@router.get("/agent-templates", response_model=ApiResponse[object])
async def list_agent_templates(db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    templates = await admin_service.list_agent_templates(db)
    return {"code": 200, "data": [AgentTemplateResponse.model_validate(t) for t in templates], "message": "ok"}


@router.put("/agent-templates/{template_id}", response_model=ApiResponse[object])
async def update_agent_template(
    template_id: uuid.UUID,
    body: AgentTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    template = await admin_service.update_agent_template(db, template_id, body)
    if template is None:
        raise HTTPException(status_code=404, detail="模板不存在")
    await admin_service.create_audit_log(
        db, user.id, "update_agent_template", "agent_template", str(template.id), {"role": template.role}
    )
    return {"code": 200, "data": AgentTemplateResponse.model_validate(template), "message": "更新成功"}


@router.get("/users", response_model=ApiResponse[object])
async def list_users(skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    items, total = await admin_service.list_users(db, skip, limit)
    return {"code": 200, "data": {"items": items, "total": total}, "message": "ok"}


@router.post("/users", response_model=ApiResponse[object])
async def create_user(body: UserCreateAdmin, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    new_user = await admin_service.create_user_admin(db, body, admin_id=user.id)
    return {"code": 200, "data": UserAdminResponse.model_validate(new_user), "message": "创建成功"}


@router.put("/users/{user_id}", response_model=ApiResponse[object])
async def update_user(user_id: uuid.UUID, body: UserUpdateAdmin, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    updated = await admin_service.update_user_admin(db, user_id, body)
    if not updated:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"code": 200, "data": UserAdminResponse.model_validate(updated), "message": "更新成功"}


@router.post("/users/{user_id}/reset-password", response_model=ApiResponse[object])
async def reset_password(user_id: uuid.UUID, body: UserResetPassword, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    success, password = await admin_service.reset_user_password(
        db, user_id, body.new_password, admin_id=user.id
    )
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"code": 200, "data": {"password": password}, "message": "密码重置成功"}


@router.delete("/users/{user_id}", response_model=ApiResponse[object])
async def delete_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    try:
        success = await admin_service.delete_user(db, user_id, admin_id=user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"code": 200, "data": None, "message": "删除成功"}


@router.get("/generation-logs", response_model=ApiResponse[object])
async def list_generation_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    items, total = await admin_service.list_generation_logs(db, skip, limit)
    return {"code": 200, "data": {"items": items, "total": total}, "message": "ok"}


@router.get("/audit-logs", response_model=ApiResponse[object])
async def list_audit_logs(skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    items, total = await admin_service.list_audit_logs(db, skip, limit)
    return {
        "code": 200,
        "data": {
            "items": [AuditLogResponse.model_validate(item) for item in items],
            "total": total,
        },
        "message": "ok",
    }


@router.get("/token-stats", response_model=ApiResponse[object])
async def get_token_stats(user_id: uuid.UUID | None = Query(None), db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    stats = await admin_service.get_token_stats(db, user_id)
    return {"code": 200, "data": stats, "message": "ok"}
