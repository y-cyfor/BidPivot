from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.common import ApiResponse
from app.api.deps import get_current_user
from app.database import get_db
from app.models.knowledge import KnowledgeDocument
from app.models.project import Project
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=ApiResponse[object])
async def dashboard_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project_total = (await db.execute(
        select(func.count()).select_from(Project).where(Project.user_id == user.id)
    )).scalar() or 0
    completed_total = (await db.execute(
        select(func.count()).select_from(Project).where(
            Project.user_id == user.id, Project.status == "completed"
        )
    )).scalar() or 0
    month_total = (await db.execute(
        select(func.count()).select_from(Project).where(
            Project.user_id == user.id,
            Project.created_at >= func.date_trunc("month", func.now()),
        )
    )).scalar() or 0
    personal_docs = (await db.execute(
        select(func.count()).select_from(KnowledgeDocument).where(
            KnowledgeDocument.user_id == user.id,
            KnowledgeDocument.scope == "personal",
        )
    )).scalar() or 0
    global_docs = (await db.execute(
        select(func.count()).select_from(KnowledgeDocument).where(
            KnowledgeDocument.scope == "global"
        )
    )).scalar() or 0

    return {
        "code": 200,
        "data": {
            "projects": project_total,
            "completed": completed_total,
            "month_projects": month_total,
            "personal_documents": personal_docs,
            "global_documents": global_docs,
        },
        "message": "ok",
    }
