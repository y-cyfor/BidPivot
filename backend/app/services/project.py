import logging
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate

logger = logging.getLogger(__name__)


async def create_project(db: AsyncSession, user_id: uuid.UUID, data: ProjectCreate) -> Project:
    project = Project(
        user_id=user_id,
        title=data.title,
        industry_tags=data.industry_tags,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def get_project(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> Project | None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_projects(db: AsyncSession, user_id: uuid.UUID, skip: int = 0, limit: int = 20) -> tuple[list[Project], int]:
    count_result = await db.execute(
        select(func.count()).select_from(Project).where(Project.user_id == user_id)
    )
    total = count_result.scalar()

    result = await db.execute(
        select(Project)
        .where(Project.user_id == user_id)
        .order_by(Project.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def update_project(db: AsyncSession, project: Project, data: ProjectUpdate) -> Project:
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project: Project) -> None:
    """Delete a project and every row that references it.

    Foreign keys are declared without ON DELETE CASCADE, so child rows must be
    removed explicitly. Stored files are removed after the transaction commits.
    """
    from app.models.generation_log import GenerationLog
    from app.models.loss_analysis import LossAnalysis
    from app.models.token_usage import TokenUsage
    from app.models.uploaded_file import UploadedFile
    from app.models.version import DocumentVersion
    from app.services import file_storage

    paths = list((await db.execute(
        select(UploadedFile.storage_path).where(UploadedFile.project_id == project.id)
    )).scalars().all())

    for model in (UploadedFile, DocumentVersion, GenerationLog, LossAnalysis, TokenUsage):
        await db.execute(delete(model).where(model.project_id == project.id))

    await db.delete(project)
    await db.commit()

    for path in paths:
        try:
            file_storage.delete_file(path)
        except Exception:
            logger.warning("Failed to delete stored file %s", path, exc_info=True)
