import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    industry_tags: Mapped[list] = mapped_column(JSONB, default=list)
    outline_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    requirements_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    full_document_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    conversation_history: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    check_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    generation_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
