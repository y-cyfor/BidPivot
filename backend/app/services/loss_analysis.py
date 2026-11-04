import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models.knowledge import KnowledgeDirectory, KnowledgeDocument
from app.models.loss_analysis import LossAnalysis
from app.services.file_parser import parse_file, validate_upload
from app.services.file_storage import upload_file as upload_to_storage
from app.services.llm_client import chat_completion
from app.services.project import get_project


async def create_analysis(db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID | None, file_bytes: bytes, filename: str) -> LossAnalysis:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    validate_upload(file_bytes, filename)
    storage_path = await run_in_threadpool(upload_to_storage, file_bytes, filename, "application/octet-stream")
    try:
        eval_content = await run_in_threadpool(parse_file, file_bytes, filename)
    except Exception as exc:
        raise ValueError(f"评标结果解析失败：{exc}") from exc
    if not eval_content.strip():
        raise ValueError("评标结果中未解析到文本内容")

    project_content = ""
    if project_id:
        project = await get_project(db, project_id, user_id)
        if project and project.full_document_json:
            for key, section in project.full_document_json.items():
                if isinstance(section, dict) and not key.startswith("_"):
                    project_content += f"\n{section.get('title', '')}: {section.get('content', '')[:500]}"

    messages = [
        {"role": "system", "content": (
            "你是一名标书分析专家。请分析评标结果，找出丢标原因并给出改进建议。\n"
            "输出JSON格式：\n"
            "{\n"
            '  "reasons": [{"category": "商务/技术/价格/资质/服务/格式", "point": "扣分点", "score": "扣分值", "description": "具体描述"}],\n'
            '  "improvements": [{"for_reason": "对应扣分点", "suggestion": "具体改进建议", "best_practice": "关联最佳实践"}],\n'
            '  "strategy": {"tech_direction": "技术方案优化方向", "pricing_strategy": "报价策略调整", "qualification": "资质补充建议", "summary": "总体策略总结"}\n'
            "}"
        )},
        {"role": "user", "content": f"评标结果：\n{eval_content[:4000]}\n\n我方标书内容：\n{project_content[:3000]}"},
    ]
    response = await chat_completion(messages, max_tokens=4096)

    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start != -1 and end > start:
            analysis_result = json.loads(response[start:end])
        else:
            analysis_result = {
                "reasons": [],
                "improvements": [],
                "strategy": {"tech_direction": "", "pricing_strategy": "", "qualification": "", "summary": response[:500]},
                "parse_error": "LLM 返回格式非标准 JSON",
            }
    except json.JSONDecodeError:
        analysis_result = {
            "reasons": [],
            "improvements": [],
            "strategy": {"tech_direction": "", "pricing_strategy": "", "qualification": "", "summary": response[:500]},
            "parse_error": "JSON 解析失败",
        }

    analysis = LossAnalysis(user_id=user_id, project_id=project_id, evaluation_file_path=storage_path, analysis_result=analysis_result)
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return analysis


async def list_analyses(db: AsyncSession, user_id: uuid.UUID) -> list[LossAnalysis]:
    result = await db.execute(select(LossAnalysis).where(LossAnalysis.user_id == user_id).order_by(LossAnalysis.created_at.desc()))
    return list(result.scalars().all())


async def get_analysis(db: AsyncSession, analysis_id: uuid.UUID, user_id: uuid.UUID) -> LossAnalysis | None:
    result = await db.execute(select(LossAnalysis).where(LossAnalysis.id == analysis_id, LossAnalysis.user_id == user_id))
    return result.scalar_one_or_none()


async def save_to_knowledge(db: AsyncSession, analysis_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    analysis = await get_analysis(db, analysis_id, user_id)
    if not analysis or not analysis.analysis_result:
        return False
    dir_result = await db.execute(
        select(KnowledgeDirectory).where(KnowledgeDirectory.user_id == user_id, KnowledgeDirectory.scope == "personal", KnowledgeDirectory.name == "丢标分析")
    )
    directory = dir_result.scalar_one_or_none()
    if not directory:
        directory = KnowledgeDirectory(user_id=user_id, scope="personal", name="丢标分析")
        db.add(directory)
        await db.flush()
    content = json.dumps(analysis.analysis_result, ensure_ascii=False, indent=2)
    doc = KnowledgeDocument(
        directory_id=directory.id, scope="personal", user_id=user_id,
        title=f"丢标分析-{analysis.created_at.strftime('%Y%m%d')}",
        file_type="json", storage_path="", content_text=content, status="draft",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    from app.services.knowledge import _index_document
    await _index_document(db, doc)
    return True
