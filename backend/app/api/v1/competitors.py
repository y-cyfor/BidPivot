import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.common import ApiResponse
from app.api.deps import get_current_user
from app.database import get_db
from app.models.competitor import CompetitorDocument
from app.models.user import User
from app.schemas.competitor import (
    AnalysisRequest, AnalysisResponse, CompetitorCreate, CompetitorDocResponse, CompetitorResponse, CompetitorUpdate,
)
from app.services import competitor as competitor_service
from app.services.file_parser import validate_upload

router = APIRouter(prefix="/competitors", tags=["competitors"])


@router.post("", response_model=ApiResponse[object])
async def create_competitor(body: CompetitorCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    comp = await competitor_service.create_competitor(db, user.id, body)
    return {"code": 200, "data": CompetitorResponse.model_validate(comp), "message": "创建成功"}


@router.get("", response_model=ApiResponse[object])
async def list_competitors(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    comps = await competitor_service.list_competitors(db, user.id)
    counts = dict((await db.execute(
        select(CompetitorDocument.competitor_id, func.count())
        .where(CompetitorDocument.user_id == user.id)
        .group_by(CompetitorDocument.competitor_id)
    )).all())
    return {
        "code": 200,
        "data": [
            CompetitorResponse.model_validate(c).model_copy(
                update={"document_count": counts.get(c.id, 0)}
            )
            for c in comps
        ],
        "message": "ok",
    }


@router.get("/{competitor_id}", response_model=ApiResponse[object])
async def get_competitor(competitor_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    comp = await competitor_service.get_competitor(db, competitor_id, user.id)
    if not comp:
        raise HTTPException(status_code=404, detail="竞品公司不存在")
    return {"code": 200, "data": CompetitorResponse.model_validate(comp), "message": "ok"}


@router.put("/{competitor_id}", response_model=ApiResponse[object])
async def update_competitor(competitor_id: uuid.UUID, body: CompetitorUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    comp = await competitor_service.update_competitor(db, competitor_id, user.id, body)
    if not comp:
        raise HTTPException(status_code=404, detail="竞品公司不存在")
    return {"code": 200, "data": CompetitorResponse.model_validate(comp), "message": "更新成功"}


@router.delete("/{competitor_id}", response_model=ApiResponse[object])
async def delete_competitor(competitor_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    success = await competitor_service.delete_competitor(db, competitor_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="竞品公司不存在")
    return {"code": 200, "data": None, "message": "删除成功"}


@router.post("/{competitor_id}/documents", response_model=ApiResponse[object])
async def upload_document(competitor_id: uuid.UUID, file: UploadFile = File(...), title: str = Form(...), file_type_tag: str = Form(...), db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    file_bytes = await file.read()
    filename = file.filename or "unknown"
    try:
        validate_upload(file_bytes, filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    doc = await competitor_service.upload_document(db, competitor_id, user.id, title, file_type_tag, file_bytes, filename)
    return {"code": 200, "data": CompetitorDocResponse.model_validate(doc), "message": "上传成功"}


@router.get("/{competitor_id}/documents", response_model=ApiResponse[object])
async def list_documents(competitor_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    docs = await competitor_service.list_documents(db, competitor_id, user.id)
    return {"code": 200, "data": [CompetitorDocResponse.model_validate(d) for d in docs], "message": "ok"}


@router.delete("/{competitor_id}/documents/{doc_id}", response_model=ApiResponse[object])
async def delete_document(doc_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    success = await competitor_service.delete_document(db, doc_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"code": 200, "data": None, "message": "删除成功"}


@router.post("/analyze", response_model=ApiResponse[object])
async def run_analysis(body: AnalysisRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    analysis = await competitor_service.run_analysis(db, user.id, body)
    return {"code": 200, "data": AnalysisResponse.model_validate(analysis), "message": "分析完成"}


@router.get("/analyses/list", response_model=ApiResponse[object])
async def list_analyses(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    analyses = await competitor_service.list_analyses(db, user.id)
    return {"code": 200, "data": [AnalysisResponse.model_validate(a) for a in analyses], "message": "ok"}


@router.post("/analyses/{analysis_id}/save-to-knowledge", response_model=ApiResponse[object])
async def save_analysis_to_knowledge(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    success = await competitor_service.save_analysis_to_knowledge(db, analysis_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="分析记录不存在或无内容")
    return {"code": 200, "data": None, "message": "已保存到知识库"}
