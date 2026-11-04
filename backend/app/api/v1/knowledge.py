import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.knowledge import (
    DirectoryCreate,
    DirectoryResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdate,
    SearchRequest,
)
from app.services import admin as admin_service
from app.services import knowledge as knowledge_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _ok(data, message: str = "ok") -> dict:
    return {"code": 200, "data": data, "message": message}


async def _create_directory(db: AsyncSession, owner_id: uuid.UUID | None, scope: str, body: DirectoryCreate) -> dict:
    directory = await knowledge_service.create_directory(db, owner_id, scope, body)
    return _ok(DirectoryResponse.model_validate(directory), "创建成功")


async def _list_directories(db: AsyncSession, owner_id: uuid.UUID | None, scope: str) -> dict:
    directories = await knowledge_service.list_directories(db, owner_id, scope)
    return _ok([DirectoryResponse.model_validate(d) for d in directories])


async def _delete_directory(db: AsyncSession, owner_id: uuid.UUID | None, scope: str, directory_id: uuid.UUID) -> dict:
    deleted, err_msg = await knowledge_service.delete_directory(db, directory_id, owner_id, scope)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    return _ok(None, "删除成功")


async def _upload_document(
    db: AsyncSession,
    owner_id: uuid.UUID | None,
    scope: str,
    directory_id: uuid.UUID,
    title: str,
    file: UploadFile,
):
    file_bytes = await file.read()
    filename = file.filename or "unknown.txt"
    try:
        return await knowledge_service.upload_document(
            db, owner_id, scope, directory_id, title, file_bytes, filename
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


async def _list_documents(
    db: AsyncSession,
    owner_id: uuid.UUID | None,
    scope: str,
    directory_id: uuid.UUID | None,
    skip: int,
    limit: int,
) -> dict:
    items, total = await knowledge_service.list_documents(
        db, owner_id, scope, directory_id, skip, limit
    )
    return _ok(DocumentListResponse(
        items=[DocumentResponse.model_validate(i) for i in items],
        total=total,
    ))


async def _get_document(db: AsyncSession, owner_id: uuid.UUID | None, scope: str, doc_id: uuid.UUID) -> dict:
    doc = await knowledge_service.get_document(db, doc_id, owner_id, scope)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    return _ok(DocumentDetailResponse.model_validate(doc))


async def _update_document(
    db: AsyncSession,
    owner_id: uuid.UUID | None,
    scope: str,
    doc_id: uuid.UUID,
    body: DocumentUpdate,
) -> dict:
    doc = await knowledge_service.update_document(db, doc_id, owner_id, scope, body)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    return _ok(DocumentResponse.model_validate(doc), "更新成功")


async def _delete_document(db: AsyncSession, owner_id: uuid.UUID | None, scope: str, doc_id: uuid.UUID) -> dict:
    deleted = await knowledge_service.delete_document(db, doc_id, owner_id, scope)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    return _ok(None, "删除成功")


async def _reindex_document(db: AsyncSession, owner_id: uuid.UUID | None, scope: str, doc_id: uuid.UUID) -> dict:
    doc = await knowledge_service.reindex_document(db, doc_id, owner_id, scope)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    return _ok(DocumentResponse.model_validate(doc), "重新索引成功")


async def _search(db: AsyncSession, user_id: uuid.UUID, body: SearchRequest, scope: str) -> dict:
    try:
        results = await knowledge_service.search_knowledge(db, user_id, body.query, scope, body.top_k)
    except knowledge_service.KnowledgeSearchError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return _ok(results)


# ==================== Personal Knowledge ====================

@router.post("/personal/directories", response_model=ApiResponse[DirectoryResponse])
async def create_personal_directory(
    body: DirectoryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _create_directory(db, user.id, "personal", body)


@router.get("/personal/directories", response_model=ApiResponse[list[DirectoryResponse]])
async def list_personal_directories(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _list_directories(db, user.id, "personal")


@router.delete("/personal/directories/{directory_id}", response_model=ApiResponse[None])
async def delete_personal_directory(
    directory_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _delete_directory(db, user.id, "personal", directory_id)


@router.post("/personal/documents/upload", response_model=ApiResponse[DocumentResponse])
async def upload_personal_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    directory_id: uuid.UUID = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = await _upload_document(db, user.id, "personal", directory_id, title, file)
    return _ok(DocumentResponse.model_validate(doc), "上传成功")


@router.get("/personal/documents", response_model=ApiResponse[DocumentListResponse])
async def list_personal_documents(
    directory_id: uuid.UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _list_documents(db, user.id, "personal", directory_id, skip, limit)


@router.get("/personal/documents/{doc_id}", response_model=ApiResponse[DocumentDetailResponse])
async def get_personal_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _get_document(db, user.id, "personal", doc_id)


@router.put("/personal/documents/{doc_id}", response_model=ApiResponse[DocumentResponse])
async def update_personal_document(
    doc_id: uuid.UUID,
    body: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _update_document(db, user.id, "personal", doc_id, body)


@router.delete("/personal/documents/{doc_id}", response_model=ApiResponse[None])
async def delete_personal_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _delete_document(db, user.id, "personal", doc_id)


@router.post("/personal/documents/{doc_id}/reindex", response_model=ApiResponse[DocumentResponse])
async def reindex_personal_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _reindex_document(db, user.id, "personal", doc_id)


@router.post("/personal/search", response_model=ApiResponse[list[dict]])
async def search_personal_knowledge(
    body: SearchRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _search(db, user.id, body, "personal")


# ==================== Global Knowledge (Admin) ====================

@router.post("/global/directories", response_model=ApiResponse[DirectoryResponse])
async def create_global_directory(
    body: DirectoryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    return await _create_directory(db, None, "global", body)


@router.get("/global/directories", response_model=ApiResponse[list[DirectoryResponse]])
async def list_global_directories(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _list_directories(db, None, "global")


@router.delete("/global/directories/{directory_id}", response_model=ApiResponse[None])
async def delete_global_directory(
    directory_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    return await _delete_directory(db, None, "global", directory_id)


@router.post("/global/documents/upload", response_model=ApiResponse[DocumentResponse])
async def upload_global_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    directory_id: uuid.UUID = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    doc = await _upload_document(db, None, "global", directory_id, title, file)
    await admin_service.create_audit_log(
        db, user.id, "upload_global_knowledge", "knowledge_document", str(doc.id), {"title": title}
    )
    return _ok(DocumentResponse.model_validate(doc), "上传成功")


@router.get("/global/documents", response_model=ApiResponse[DocumentListResponse])
async def list_global_documents(
    directory_id: uuid.UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _list_documents(db, None, "global", directory_id, skip, limit)


@router.get("/global/documents/{doc_id}", response_model=ApiResponse[DocumentDetailResponse])
async def get_global_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _get_document(db, None, "global", doc_id)


@router.put("/global/documents/{doc_id}", response_model=ApiResponse[DocumentResponse])
async def update_global_document(
    doc_id: uuid.UUID,
    body: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    return await _update_document(db, None, "global", doc_id, body)


@router.delete("/global/documents/{doc_id}", response_model=ApiResponse[None])
async def delete_global_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    return await _delete_document(db, None, "global", doc_id)


@router.post("/global/documents/{doc_id}/reindex", response_model=ApiResponse[DocumentResponse])
async def reindex_global_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    return await _reindex_document(db, None, "global", doc_id)


@router.post("/global/documents/{doc_id}/publish", response_model=ApiResponse[DocumentResponse])
async def publish_global_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    doc = await knowledge_service.publish_document(db, doc_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    await admin_service.create_audit_log(
        db, user.id, "publish_global_knowledge", "knowledge_document", str(doc.id), {"title": doc.title}
    )
    return _ok(DocumentResponse.model_validate(doc), "发布成功")


@router.post("/global/search", response_model=ApiResponse[list[dict]])
async def search_global_knowledge(
    body: SearchRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _search(db, user.id, body, "global")
