import uuid
from datetime import datetime

from pydantic import BaseModel


class VersionResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    version_number: int
    content_html: str | None
    created_by: str
    instruction: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VersionListResponse(BaseModel):
    items: list[VersionResponse]
    total: int


class ConversationMessage(BaseModel):
    role: str
    content: str
    timestamp: str


class ConversationRequest(BaseModel):
    instruction: str
    selected_text: str | None = None
    current_html: str
