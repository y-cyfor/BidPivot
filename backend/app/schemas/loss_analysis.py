import uuid
from datetime import datetime

from pydantic import BaseModel


class LossAnalysisCreate(BaseModel):
    project_id: uuid.UUID | None = None


class LossAnalysisResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID | None
    evaluation_file_path: str
    analysis_result: dict | None
    created_at: datetime
    model_config = {"from_attributes": True}
