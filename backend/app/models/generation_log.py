import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class GenerationLog(Base):
    __tablename__ = "generation_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    agents_used: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
