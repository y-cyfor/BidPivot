import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.common import ApiResponse
from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.loss_analysis import LossAnalysisResponse
from app.services import loss_analysis as loss_service

router = APIRouter(prefix="/loss-analysis", tags=["loss-analysis"])


@router.post("", response_model=ApiResponse[object])
async def create_analysis(file: UploadFile = File(...), project_id: uuid.UUID | None = Form(None), db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    file_bytes = await file.read()
    filename = file.filename or "unknown"
    try:
        analysis = await loss_service.create_analysis(db, user.id, project_id, file_bytes, filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"code": 200, "data": LossAnalysisResponse.model_validate(analysis), "message": "分析完成"}


@router.get("", response_model=ApiResponse[object])
async def list_analyses(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    analyses = await loss_service.list_analyses(db, user.id)
    return {"code": 200, "data": [LossAnalysisResponse.model_validate(a) for a in analyses], "message": "ok"}


@router.get("/{analysis_id}", response_model=ApiResponse[object])
async def get_analysis(analysis_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    analysis = await loss_service.get_analysis(db, analysis_id, user.id)
    if not analysis:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    return {"code": 200, "data": LossAnalysisResponse.model_validate(analysis), "message": "ok"}


@router.post("/{analysis_id}/save-to-knowledge", response_model=ApiResponse[object])
async def save_to_knowledge(analysis_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    success = await loss_service.save_to_knowledge(db, analysis_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="分析记录不存在或无内容")
    return {"code": 200, "data": None, "message": "已保存到知识库"}
