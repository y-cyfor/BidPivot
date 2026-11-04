import uuid
from datetime import datetime

from pydantic import BaseModel


class DirectoryCreate(BaseModel):
    name: str
    parent_id: uuid.UUID | None = None


class DirectoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    scope: str
    parent_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentUpload(BaseModel):
    title: str
    directory_id: uuid.UUID


class DocumentResponse(BaseModel):
    id: uuid.UUID
    title: str
    file_type: str
    status: str
    directory_id: uuid.UUID
    scope: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentDetailResponse(DocumentResponse):
    content_text: str | None = None
    published_content_text: str | None = None
    published_at: datetime | None = None


class DocumentUpdate(BaseModel):
    title: str | None = None
    content_text: str | None = None


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10


class SearchResult(BaseModel):
    chunk_text: str
    document_id: uuid.UUID
    document_title: str
    score: float
    metadata: dict
