import secrets
import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models.agent_template import AgentTemplate
from app.models.audit_log import AuditLog
from app.models.generation_log import GenerationLog
from app.models.project import Project
from app.models.login_history import LoginHistory
from app.models.model_config import ModelConfig
from app.models.token_usage import TokenUsage
from app.models.user import User
from app.schemas.admin import (
    AgentTemplateUpdate,
    ModelConfigCreate,
    ModelConfigUpdate,
    UserCreateAdmin,
    UserUpdateAdmin,
)
from app.utils.security import hash_password
from app.utils.crypto import encrypt_api_key


async def get_model_configs(db: AsyncSession, type: str | None = None) -> list[ModelConfig]:
    stmt = select(ModelConfig)
    if type:
        stmt = stmt.where(ModelConfig.type == type)
    result = await db.execute(stmt.order_by(ModelConfig.created_at.desc()))
    return list(result.scalars().all())


async def _deactivate_other_configs(db: AsyncSession, config_type: str, exclude_id: uuid.UUID | None = None) -> None:
    stmt = update(ModelConfig).where(
        ModelConfig.type == config_type,
        ModelConfig.is_active.is_(True),
    )
    if exclude_id is not None:
        stmt = stmt.where(ModelConfig.id != exclude_id)
    await db.execute(stmt.values(is_active=False))


async def update_model_config(db: AsyncSession, config_id: uuid.UUID, data: ModelConfigUpdate) -> ModelConfig | None:
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "api_key":
            if value:
                config.api_key_encrypted = encrypt_api_key(value)
        else:
            setattr(config, key, value)
    if config.is_active:
        await _deactivate_other_configs(db, config.type, exclude_id=config.id)
    await db.commit()
    await db.refresh(config)
    # Clear LLM/Embedding config cache so next request uses updated config
    from app.services.llm_client import clear_llm_config_cache
    clear_llm_config_cache()
    return config


async def create_model_config(db: AsyncSession, data: ModelConfigCreate) -> ModelConfig:
    if data.is_active:
        await _deactivate_other_configs(db, data.type)
    config = ModelConfig(
        type=data.type,
        provider_name=data.provider_name,
        api_base=data.api_base,
        api_key_encrypted=encrypt_api_key(data.api_key),
        model_name=data.model_name,
        parameters=data.parameters,
        is_active=data.is_active,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    from app.services.llm_client import clear_llm_config_cache
    clear_llm_config_cache()
    return config


async def list_agent_templates(db: AsyncSession) -> list[AgentTemplate]:
    result = await db.execute(select(AgentTemplate).order_by(AgentTemplate.role))
    return list(result.scalars().all())


async def update_agent_template(
    db: AsyncSession, template_id: uuid.UUID, data: AgentTemplateUpdate
) -> AgentTemplate | None:
    result = await db.execute(select(AgentTemplate).where(AgentTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if template is None:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(template, key, value)
    await db.commit()
    await db.refresh(template)
    from app.services.agents.writer import clear_agent_prompt_cache
    clear_agent_prompt_cache()
    return template


async def list_users(db: AsyncSession, skip: int = 0, limit: int = 50) -> tuple[list[dict], int]:
    count_result = await db.execute(select(func.count()).select_from(User))
    total = count_result.scalar() or 0
    result = await db.execute(select(User).order_by(User.created_at.desc()).offset(skip).limit(limit))
    users = result.scalars().all()
    user_list = []
    for u in users:
        login_result = await db.execute(
            select(LoginHistory.login_time).where(LoginHistory.user_id == u.id, LoginHistory.status == "success").order_by(LoginHistory.login_time.desc()).limit(1)
        )
        last_login = login_result.scalar_one_or_none()
        token_result = await db.execute(select(func.coalesce(func.sum(TokenUsage.total_tokens), 0)).where(TokenUsage.user_id == u.id))
        total_tokens = token_result.scalar() or 0
        user_list.append({"id": u.id, "username": u.username, "role": u.role, "is_active": True, "created_at": u.created_at, "last_login": last_login, "total_tokens": total_tokens})
    return user_list, total


async def create_user_admin(db: AsyncSession, data: UserCreateAdmin, admin_id: uuid.UUID | None = None) -> User:
    user = User(username=data.username, password_hash=hash_password(data.password), role=data.role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    if admin_id:
        await create_audit_log(db, admin_id, "create_user", "user", str(user.id), {"username": data.username, "role": data.role})
    return user


async def update_user_admin(db: AsyncSession, user_id: uuid.UUID, data: UserUpdateAdmin) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return user


async def reset_user_password(
    db: AsyncSession,
    user_id: uuid.UUID,
    new_password: str | None = None,
    admin_id: uuid.UUID | None = None,
) -> tuple[bool, str | None]:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return False, None
    password = new_password or secrets.token_urlsafe(9)
    user.password_hash = hash_password(password)
    await db.commit()
    if admin_id:
        await create_audit_log(db, admin_id, "reset_password", "user", str(user_id), {"username": user.username})
    return True, password


async def delete_user(db: AsyncSession, user_id: uuid.UUID, admin_id: uuid.UUID | None = None) -> bool:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return False
    if admin_id == user_id:
        raise ValueError("不能删除当前登录用户")
    username = user.username

    from app.models.competitor import Competitor, CompetitorAnalysis, CompetitorDocument
    from app.models.generation_log import GenerationLog
    from app.models.knowledge import KnowledgeChunk, KnowledgeDirectory, KnowledgeDocument
    from app.models.loss_analysis import LossAnalysis
    from app.models.project import Project
    from app.models.uploaded_file import UploadedFile
    from app.services import file_storage, vector_store
    from app.services.project import delete_project

    projects = list((await db.execute(select(Project).where(Project.user_id == user_id))).scalars().all())
    for project in projects:
        await delete_project(db, project)

    knowledge_paths = list((await db.execute(
        select(KnowledgeDocument.storage_path).where(KnowledgeDocument.user_id == user_id)
    )).scalars().all())
    doc_ids = list((await db.execute(
        select(KnowledgeDocument.id).where(KnowledgeDocument.user_id == user_id)
    )).scalars().all())
    if doc_ids:
        await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id.in_(doc_ids)))
    await db.execute(
        update(KnowledgeDirectory).where(KnowledgeDirectory.user_id == user_id).values(parent_id=None)
    )
    await db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.user_id == user_id))
    await db.execute(delete(KnowledgeDirectory).where(KnowledgeDirectory.user_id == user_id))

    competitor_paths = list((await db.execute(
        select(CompetitorDocument.storage_path).where(CompetitorDocument.user_id == user_id)
    )).scalars().all())
    await db.execute(delete(CompetitorDocument).where(CompetitorDocument.user_id == user_id))
    await db.execute(delete(CompetitorAnalysis).where(CompetitorAnalysis.user_id == user_id))
    await db.execute(delete(Competitor).where(Competitor.user_id == user_id))

    for model in (LossAnalysis, TokenUsage, GenerationLog, AuditLog, LoginHistory, UploadedFile):
        await db.execute(delete(model).where(model.user_id == user_id))

    await db.delete(user)
    await db.commit()

    try:
        await run_in_threadpool(vector_store.delete_collection, f"personal_{user_id}")
    except Exception:
        pass
    for path in [*knowledge_paths, *competitor_paths]:
        try:
            file_storage.delete_file(path)
        except Exception:
            pass

    if admin_id:
        await create_audit_log(db, admin_id, "delete_user", "user", str(user_id), {"username": username})
    return True


async def list_generation_logs(db: AsyncSession, skip: int = 0, limit: int = 50) -> tuple[list[dict], int]:
    total = (await db.execute(select(func.count()).select_from(GenerationLog))).scalar() or 0
    rows = (await db.execute(
        select(GenerationLog, Project.title, User.username)
        .join(Project, Project.id == GenerationLog.project_id)
        .join(User, User.id == GenerationLog.user_id)
        .order_by(GenerationLog.start_time.desc())
        .offset(skip)
        .limit(limit)
    )).all()
    items = []
    for log, project_title, username in rows:
        duration = None
        if log.end_time and log.start_time:
            duration = round((log.end_time - log.start_time).total_seconds(), 1)
        items.append({
            "id": str(log.id),
            "project_id": str(log.project_id),
            "project_title": project_title,
            "username": username,
            "task_id": log.task_id,
            "status": log.status,
            "final_score": log.final_score,
            "agents_used": log.agents_used or [],
            "start_time": log.start_time.isoformat() if log.start_time else None,
            "end_time": log.end_time.isoformat() if log.end_time else None,
            "duration_seconds": duration,
        })
    return items, total


async def list_audit_logs(db: AsyncSession, skip: int = 0, limit: int = 50) -> tuple[list, int]:
    count_result = await db.execute(select(func.count()).select_from(AuditLog))
    total = count_result.scalar() or 0
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit))
    return list(result.scalars().all()), total


async def create_audit_log(db: AsyncSession, user_id: uuid.UUID, action: str, target_type: str = None, target_id: str = None, details: dict = None, ip_address: str = None):
    log = AuditLog(user_id=user_id, action=action, target_type=target_type, target_id=target_id, details=details, ip_address=ip_address)
    db.add(log)
    await db.commit()


async def get_token_stats(db: AsyncSession, user_id: uuid.UUID | None = None) -> list[dict]:
    stmt = select(TokenUsage.user_id, func.sum(TokenUsage.total_tokens).label("total_tokens")).group_by(TokenUsage.user_id)
    if user_id:
        stmt = stmt.where(TokenUsage.user_id == user_id)
    result = await db.execute(stmt)
    stats = []
    for row in result.all():
        user_result = await db.execute(select(User.username).where(User.id == row.user_id))
        username = user_result.scalar_one_or_none() or "unknown"
        session_stmt = select(TokenUsage.session_id, func.sum(TokenUsage.total_tokens).label("session_tokens")).where(TokenUsage.user_id == row.user_id).group_by(TokenUsage.session_id)
        session_result = await db.execute(session_stmt)
        sessions = [{"session_id": s.session_id, "tokens": s.session_tokens} for s in session_result.all()]
        stats.append({"user_id": str(row.user_id), "username": username, "total_tokens": row.total_tokens, "session_tokens": sessions})
    return stats
