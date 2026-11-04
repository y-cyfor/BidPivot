import uuid
from datetime import datetime

from pydantic import BaseModel


class CompetitorCreate(BaseModel):
    name: str
    industry: str | None = None
    description: str | None = None


class CompetitorUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    description: str | None = None


class CompetitorResponse(BaseModel):
    id: uuid.UUID
    name: str
    industry: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    model_config = {"from_attributes": True}


class CompetitorDocCreate(BaseModel):
    title: str
    file_type_tag: str


class CompetitorDocResponse(BaseModel):
    id: uuid.UUID
    competitor_id: uuid.UUID
    title: str
    file_type_tag: str
    content_text: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class AnalysisRequest(BaseModel):
    analysis_type: str
    competitor_ids: list[uuid.UUID]


class AnalysisResponse(BaseModel):
    id: uuid.UUID
    analysis_type: str
    competitor_ids: list
    report_content: str | None
    created_at: datetime
    model_config = {"from_attributes": True}
