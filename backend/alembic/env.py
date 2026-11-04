import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.database import Base

# Import all models here so Alembic can detect them
from app.models.user import User  # noqa: F401
from app.models.project import Project  # noqa: F401
from app.models.uploaded_file import UploadedFile  # noqa: F401
from app.models.knowledge import KnowledgeDirectory, KnowledgeDocument, KnowledgeChunk  # noqa: F401
from app.models.competitor import Competitor, CompetitorDocument, CompetitorAnalysis  # noqa: F401
from app.models.loss_analysis import LossAnalysis  # noqa: F401
from app.models.model_config import ModelConfig  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.login_history import LoginHistory  # noqa: F401
from app.models.token_usage import TokenUsage  # noqa: F401
from app.models.version import DocumentVersion  # noqa: F401
from app.models.generation_log import GenerationLog  # noqa: F401
from app.models.agent_template import AgentTemplate  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
