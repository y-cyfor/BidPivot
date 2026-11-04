import io
import re
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.schemas.common import ApiResponse
from app.api.deps import get_current_user
from app.database import get_db
from app.models.project import Project
from app.models.uploaded_file import UploadedFile
from app.models.user import User
from app.services import file_parser, file_storage
from app.utils import virus_scan

router = APIRouter(prefix="/files", tags=["files"])

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "md", "xlsx", "xls"}
ALLOWED_FILE_TYPES = {"bid", "competitor", "other"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("/upload", response_model=ApiResponse[object])
async def upload_file(
    file: UploadFile = File(...),
    project_id: uuid.UUID | None = Form(None),
    file_type: str = Form("other"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的文件类型: .{ext}")
    if file_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的文件分类")

    if project_id is not None:
        owned = await db.execute(
            select(Project.id).where(Project.id == project_id, Project.user_id == user.id)
        )
        if owned.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    file_bytes = await file.read()

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="文件大小超过限制（50MB）")

    try:
        file_parser.validate_file_signature(file_bytes, ext)
        await run_in_threadpool(virus_scan.scan_bytes, file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    safe_filename = re.sub(r'[^\w\-_\.]', '_', file.filename or "upload")
    storage_path = await run_in_threadpool(
        file_storage.upload_file, file_bytes, safe_filename, file.content_type or "application/octet-stream"
    )

    parse_status = "pending"
    parsed_content = None
    try:
        parsed_content = await run_in_threadpool(file_parser.parse_file, file_bytes, file.filename)
        parse_status = "completed"
    except Exception:
        parse_status = "failed"

    uploaded = UploadedFile(
        project_id=project_id,
        user_id=user.id,
        file_type=file_type,
        original_name=file.filename,
        storage_path=storage_path,
        parse_status=parse_status,
        parsed_content=parsed_content,
    )
    db.add(uploaded)
    await db.commit()
    await db.refresh(uploaded)

    return {
        "code": 200,
        "data": {
            "id": str(uploaded.id),
            "original_name": uploaded.original_name,
            "parse_status": uploaded.parse_status,
        },
        "message": "上传成功",
    }


@router.get("", response_model=ApiResponse[object])
async def list_files(
    project_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(UploadedFile).where(UploadedFile.user_id == user.id)
    if project_id is not None:
        stmt = stmt.where(UploadedFile.project_id == project_id)
    files = (await db.execute(stmt.order_by(UploadedFile.created_at.desc()))).scalars().all()
    return {
        "code": 200,
        "data": [
            {
                "id": str(item.id),
                "original_name": item.original_name,
                "file_type": item.file_type,
                "parse_status": item.parse_status,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in files
        ],
        "message": "ok",
    }


@router.get("/{file_id}", response_model=ApiResponse[object])
async def get_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    uploaded = (await db.execute(
        select(UploadedFile).where(UploadedFile.id == file_id, UploadedFile.user_id == user.id)
    )).scalar_one_or_none()
    if uploaded is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    return {
        "code": 200,
        "data": {
            "id": str(uploaded.id),
            "original_name": uploaded.original_name,
            "file_type": uploaded.file_type,
            "parse_status": uploaded.parse_status,
            "parsed_chars": len(uploaded.parsed_content or ""),
        },
        "message": "ok",
    }


@router.get("/{file_id}/download")
async def download_uploaded_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    uploaded = (await db.execute(
        select(UploadedFile).where(UploadedFile.id == file_id, UploadedFile.user_id == user.id)
    )).scalar_one_or_none()
    if uploaded is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    try:
        content = await run_in_threadpool(file_storage.download_file, uploaded.storage_path)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件已丢失") from exc

    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="download"'},
    )
