import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models.competitor import Competitor, CompetitorAnalysis, CompetitorDocument
from app.schemas.competitor import AnalysisRequest, CompetitorCreate, CompetitorUpdate
from app.services import file_storage, vector_store
from app.services.file_parser import parse_file
from app.services.file_storage import upload_file as upload_to_storage
from app.services.llm_client import chat_completion, get_embedding, get_embeddings_batch

logger = logging.getLogger(__name__)


async def create_competitor(db: AsyncSession, user_id: uuid.UUID, data: CompetitorCreate) -> Competitor:
    competitor = Competitor(user_id=user_id, name=data.name, industry=data.industry, description=data.description)
    db.add(competitor)
    await db.commit()
    await db.refresh(competitor)
    return competitor


async def list_competitors(db: AsyncSession, user_id: uuid.UUID) -> list[Competitor]:
    result = await db.execute(select(Competitor).where(Competitor.user_id == user_id).order_by(Competitor.created_at.desc()))
    return list(result.scalars().all())


async def get_competitor(db: AsyncSession, competitor_id: uuid.UUID, user_id: uuid.UUID) -> Competitor | None:
    result = await db.execute(select(Competitor).where(Competitor.id == competitor_id, Competitor.user_id == user_id))
    return result.scalar_one_or_none()


async def update_competitor(db: AsyncSession, competitor_id: uuid.UUID, user_id: uuid.UUID, data: CompetitorUpdate) -> Competitor | None:
    competitor = await get_competitor(db, competitor_id, user_id)
    if not competitor:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(competitor, key, value)
    await db.commit()
    await db.refresh(competitor)
    return competitor


async def delete_competitor(db: AsyncSession, competitor_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    competitor = await get_competitor(db, competitor_id, user_id)
    if not competitor:
        return False
    collection = f"competitor_{user_id}"
    docs = list((await db.execute(
        select(CompetitorDocument).where(CompetitorDocument.competitor_id == competitor_id)
    )).scalars().all())
    paths = [doc.storage_path for doc in docs]
    for doc in docs:
        try:
            await run_in_threadpool(vector_store.delete_by_document, collection, str(doc.id))
        except Exception:
            pass
        await db.delete(doc)
    await db.delete(competitor)
    await db.commit()
    for path in paths:
        try:
            await run_in_threadpool(file_storage.delete_file, path)
        except Exception:
            logger.warning("Failed to delete competitor file %s", path, exc_info=True)
    return True


async def upload_document(db: AsyncSession, competitor_id: uuid.UUID, user_id: uuid.UUID, title: str, file_type_tag: str, file_bytes: bytes, filename: str) -> CompetitorDocument:
    storage_path = await run_in_threadpool(upload_to_storage, file_bytes, filename, "application/octet-stream")
    content_text = ""
    try:
        content_text = await run_in_threadpool(parse_file, file_bytes, filename)
    except Exception:
        pass
    doc = CompetitorDocument(competitor_id=competitor_id, user_id=user_id, title=title, file_type_tag=file_type_tag, storage_path=storage_path, content_text=content_text)
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    if content_text:
        collection = f"competitor_{user_id}"
        texts = [content_text[i:i + 800] for i in range(0, len(content_text), 800)]
        try:
            vectors = await get_embeddings_batch(texts)
        except Exception as exc:
            logger.warning("Embedding failed for competitor document %s: %s", doc.id, exc)
            vectors = []

        if vectors and len(vectors) == len(texts):
            dims = {len(vector) for vector in vectors}
            if len(dims) == 1:
                await run_in_threadpool(vector_store.ensure_collection, collection, dims.pop())
                chunks = [
                    {
                        "id": str(uuid.uuid4()),
                        "vector": vectors[idx],
                        "payload": {
                            "text": chunk_text,
                            "document_id": str(doc.id),
                            "competitor_id": str(competitor_id),
                        },
                    }
                    for idx, chunk_text in enumerate(texts)
                ]
                await run_in_threadpool(vector_store.upsert_chunks, collection, chunks)
    return doc


async def list_documents(db: AsyncSession, competitor_id: uuid.UUID, user_id: uuid.UUID) -> list[CompetitorDocument]:
    result = await db.execute(select(CompetitorDocument).where(CompetitorDocument.competitor_id == competitor_id, CompetitorDocument.user_id == user_id).order_by(CompetitorDocument.created_at.desc()))
    return list(result.scalars().all())


async def delete_document(db: AsyncSession, doc_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    result = await db.execute(select(CompetitorDocument).where(CompetitorDocument.id == doc_id, CompetitorDocument.user_id == user_id))
    doc = result.scalar_one_or_none()
    if not doc:
        return False
    collection = f"competitor_{user_id}"
    storage_path = doc.storage_path
    try:
        await run_in_threadpool(vector_store.delete_by_document, collection, str(doc.id))
    except Exception:
        pass
    await db.delete(doc)
    await db.commit()
    try:
        await run_in_threadpool(file_storage.delete_file, storage_path)
    except Exception:
        logger.warning("Failed to delete competitor file %s", storage_path, exc_info=True)
    return True


async def run_analysis(db: AsyncSession, user_id: uuid.UUID, data: AnalysisRequest) -> CompetitorAnalysis:
    prompt_type = "对比分析多个竞品公司之间的差异" if data.analysis_type == "competitor_vs_competitor" else "对比分析我方公司与竞品公司的差异"

    retrieved_by_competitor: dict[str, list[str]] = {}
    try:
        query = prompt_type + " " + " ".join(str(cid) for cid in data.competitor_ids)
        query_vector = await get_embedding(query)
        collection = f"competitor_{user_id}"
        if await run_in_threadpool(vector_store.collection_exists, collection):
            results = await run_in_threadpool(vector_store.search, collection, query_vector, 20)
            for result in results:
                payload = result.get("payload", {})
                cid = payload.get("competitor_id")
                if cid and payload.get("text"):
                    retrieved_by_competitor.setdefault(str(cid), []).append(payload["text"])
    except Exception as exc:
        logger.warning("Competitor vector retrieval failed: %s", exc)

    competitors_info = []
    for cid in data.competitor_ids:
        comp = await get_competitor(db, cid, user_id)
        if not comp:
            continue
        doc_texts = [f"[检索片段] {text[:500]}" for text in retrieved_by_competitor.get(str(cid), [])[:5]]
        if not doc_texts:
            docs = await list_documents(db, cid, user_id)
            doc_texts = [f"[{d.file_type_tag}] {d.title}: {(d.content_text or '')[:500]}" for d in docs[:5]]
        competitors_info.append({
            "name": comp.name,
            "industry": comp.industry or "",
            "description": comp.description or "",
            "documents": doc_texts,
        })

    competitors_text = ""
    for ci in competitors_info:
        competitors_text += f"\n\n竞品公司：{ci['name']}\n行业：{ci['industry']}\n简介：{ci['description']}\n资料：\n" + "\n".join(ci["documents"])

    messages = [
        {"role": "system", "content": f"你是一名竞品分析专家。请{prompt_type}。输出格式：1.技术方案对比 2.定价策略差异 3.客户群体差异 4.资质优劣势 5.服务差异 6.总结与建议"},
        {"role": "user", "content": f"竞品信息：{competitors_text[:6000]}"},
    ]
    report = await chat_completion(messages, max_tokens=4096)

    analysis = CompetitorAnalysis(user_id=user_id, analysis_type=data.analysis_type, competitor_ids=[str(cid) for cid in data.competitor_ids], report_content=report)
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return analysis


async def save_analysis_to_knowledge(db: AsyncSession, analysis_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Save competitor analysis to knowledge base."""
    from app.models.knowledge import KnowledgeDirectory, KnowledgeDocument

    result = await db.execute(
        select(CompetitorAnalysis).where(CompetitorAnalysis.id == analysis_id, CompetitorAnalysis.user_id == user_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis or not analysis.report_content:
        return False

    dir_result = await db.execute(
        select(KnowledgeDirectory).where(
            KnowledgeDirectory.user_id == user_id,
            KnowledgeDirectory.scope == "personal",
            KnowledgeDirectory.name == "竞品分析",
        )
    )
    directory = dir_result.scalar_one_or_none()
    if not directory:
        directory = KnowledgeDirectory(user_id=user_id, scope="personal", name="竞品分析")
        db.add(directory)
        await db.flush()

    doc = KnowledgeDocument(
        directory_id=directory.id, scope="personal", user_id=user_id,
        title=f"竞品分析-{analysis.created_at.strftime('%Y%m%d')}",
        file_type="md", storage_path="",
        content_text=analysis.report_content, status="draft",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    from app.services.knowledge import _index_document
    await _index_document(db, doc)
    return True


async def list_analyses(db: AsyncSession, user_id: uuid.UUID) -> list[CompetitorAnalysis]:
    result = await db.execute(select(CompetitorAnalysis).where(CompetitorAnalysis.user_id == user_id).order_by(CompetitorAnalysis.created_at.desc()))
    return list(result.scalars().all())
