import uuid
from datetime import datetime

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    title: str
    industry_tags: list[str] = []


class ProjectUpdate(BaseModel):
    title: str | None = None
    industry_tags: list[str] | None = None
    status: str | None = None
    outline_json: dict | None = None
    requirements_json: dict | None = None
    full_document_json: dict | None = None
    content_html: str | None = None
    content_json: dict | None = None


class ProjectUpdatePublic(BaseModel):
    """Fields a normal client may change through the generic project endpoint."""

    title: str | None = None
    industry_tags: list[str] | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    status: str
    industry_tags: list[str]
    content_html: str | None = None
    content_json: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectDetailResponse(ProjectResponse):
    """Full project payload, only used by the detail endpoints.

    List endpoints intentionally keep using ``ProjectResponse`` so that a page
    of projects does not carry every outline and document body.
    """

    outline_json: dict | None = None
    requirements_json: dict | None = None
    full_document_json: dict | None = None
    conversation_history: list[dict] | None = None
    check_report: dict | None = None
    generation_task_id: str | None = None



class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
