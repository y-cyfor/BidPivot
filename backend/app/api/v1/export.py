import io
import re
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.project import get_project

router = APIRouter(prefix="/export", tags=["export"])


def _content_disposition(filename: str) -> str:
    """Build an RFC 5987 compliant Content-Disposition header.

    Starlette encodes response headers as latin-1, so a raw Chinese filename
    raises UnicodeEncodeError. Keep an ASCII fallback plus filename* for the
    UTF-8 name.
    """
    safe_name = re.sub(r'[\x00-\x1f\x7f"\\/]', "_", filename).strip() or "bid"
    suffix = ""
    if "." in safe_name:
        suffix = "." + safe_name.rsplit(".", 1)[-1]
    fallback = f"bid{suffix}" if suffix.isascii() else "bid"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(safe_name)}"



@router.get("/{project_id}")
async def export_project(
    project_id: uuid.UUID,
    format: str = "docx",
    template: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = await get_project(db, project_id, user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    content_html = getattr(project, "content_html", None) or ""
    if not content_html and project.full_document_json:
        content_html = _build_html_from_json(project.full_document_json)

    title = project.title

    template_config = None
    if template:
        import json
        try:
            template_config = json.loads(template)
        except json.JSONDecodeError:
            pass

    if format == "docx":
        from app.services.exporter import export_to_docx_with_template
        file_bytes = await run_in_threadpool(
            export_to_docx_with_template, title, content_html, template_config
        )
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{title}.docx"
    elif format == "pdf":
        from app.services.exporter import export_to_pdf
        file_bytes = await run_in_threadpool(export_to_pdf, title, content_html, template_config)
        media_type = "application/pdf"
        filename = f"{title}.pdf"
    elif format in ("md", "markdown"):
        from app.services.exporter import export_to_markdown
        file_bytes = await run_in_threadpool(export_to_markdown, title, content_html)
        media_type = "text/markdown; charset=utf-8"
        filename = f"{title}.md"
    else:
        raise HTTPException(status_code=400, detail="不支持的格式，可选: docx, pdf, md")

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": _content_disposition(filename)},
    )


def _build_html_from_json(document_json: dict) -> str:
    sections = document_json.get("sections", document_json)
    html_parts: list[str] = []
    if isinstance(sections, dict):
        items = sections.items()
    elif isinstance(sections, list):
        items = enumerate(sections)
    else:
        return ""
    for _, section in items:
        if not isinstance(section, dict):
            continue
        sec_title = section.get("title", "")
        if sec_title:
            html_parts.append(f"<h2>{sec_title}</h2>")
        content = section.get("content", "")
        for para in content.split("\n"):
            if para.strip():
                html_parts.append(f"<p>{para}</p>")
    return "\n".join(html_parts)
