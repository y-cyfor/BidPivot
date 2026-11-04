import logging
import mimetypes
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models.knowledge import KnowledgeChunk, KnowledgeDirectory, KnowledgeDocument
from app.schemas.knowledge import DirectoryCreate, DocumentUpdate
from app.services import file_parser, file_storage, vector_store
from app.services.llm_client import get_embedding, get_embeddings_batch
from app.utils import virus_scan

logger = logging.getLogger(__name__)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
ALLOWED_KNOWLEDGE_EXTENSIONS = {"pdf", "docx", "txt", "md", "xlsx", "xls"}
MAX_KNOWLEDGE_FILE_SIZE = 50 * 1024 * 1024


class KnowledgeSearchError(RuntimeError):
    """Raised when retrieval cannot run because of configuration/backends."""


def _keyword_overlap(query: str, text: str) -> float:
    terms = set(re.findall(r"[\u4e00-\u9fa5]{2,}|[A-Za-z0-9]+", query))
    if not terms:
        return 0.0
    hits = sum(1 for term in terms if term in text)
    return hits / len(terms)


def _collection_name(scope: str, user_id: uuid.UUID | None = None) -> str:
    if scope == "personal" and user_id:
        return f"personal_{user_id}"
    return "global"


def _split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text on paragraph/heading boundaries, then hard-wrap long blocks."""
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []

    blocks = [b.strip() for b in re.split(r"\n\s*\n|\n(?=#{1,4}\s)", text) if b.strip()]
    chunks: list[str] = []
    current = ""

    for block in blocks:
        if len(block) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(block):
                end = min(start + chunk_size, len(block))
                chunks.append(block[start:end])
                if end >= len(block):
                    break
                start = end - overlap
            continue

        candidate = f"{current}\n{block}" if current else block
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
                current = f"{current[-overlap:]}\n{block}".strip() if overlap else block
            else:
                current = block

    if current:
        chunks.append(current)
    return chunks


async def create_directory(db: AsyncSession, user_id: uuid.UUID | None, scope: str, data: DirectoryCreate) -> KnowledgeDirectory:
    directory = KnowledgeDirectory(
        scope=scope,
        user_id=user_id if scope == "personal" else None,
        parent_id=data.parent_id,
        name=data.name,
    )
    db.add(directory)
    await db.commit()
    await db.refresh(directory)
    return directory


async def list_directories(db: AsyncSession, user_id: uuid.UUID | None, scope: str) -> list[KnowledgeDirectory]:
    stmt = select(KnowledgeDirectory).where(KnowledgeDirectory.scope == scope)
    if scope == "personal" and user_id:
        stmt = stmt.where(KnowledgeDirectory.user_id == user_id)
    elif scope == "global":
        stmt = stmt.where(KnowledgeDirectory.user_id.is_(None))
    stmt = stmt.order_by(KnowledgeDirectory.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_directory(db: AsyncSession, directory_id: uuid.UUID, user_id: uuid.UUID | None, scope: str) -> tuple[bool, str]:
    """Delete a directory. Returns (success, error_message)."""
    stmt = select(KnowledgeDirectory).where(KnowledgeDirectory.id == directory_id, KnowledgeDirectory.scope == scope)
    if scope == "personal" and user_id:
        stmt = stmt.where(KnowledgeDirectory.user_id == user_id)
    result = await db.execute(stmt)
    directory = result.scalar_one_or_none()
    if directory is None:
        return False, "目录不存在"

    # Check for associated documents
    doc_count_stmt = select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.directory_id == directory_id)
    doc_count_result = await db.execute(doc_count_stmt)
    doc_count = doc_count_result.scalar() or 0
    if doc_count > 0:
        return False, f"目录下有 {doc_count} 个文档，请先删除文档"

    child_count = (await db.execute(
        select(func.count()).select_from(KnowledgeDirectory).where(KnowledgeDirectory.parent_id == directory_id)
    )).scalar() or 0
    if child_count > 0:
        return False, f"目录下有 {child_count} 个子目录，请先删除子目录"

    await db.delete(directory)
    await db.commit()
    return True, ""


async def upload_document(
    db: AsyncSession, user_id: uuid.UUID | None, scope: str,
    directory_id: uuid.UUID, title: str, file_bytes: bytes, filename: str,
) -> KnowledgeDocument:
    file_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if file_ext not in ALLOWED_KNOWLEDGE_EXTENSIONS:
        raise ValueError(f"不支持的文件类型: .{file_ext}")
    if len(file_bytes) > MAX_KNOWLEDGE_FILE_SIZE:
        raise ValueError("文件大小超过限制（50MB）")

    dir_stmt = select(KnowledgeDirectory).where(
        KnowledgeDirectory.id == directory_id,
        KnowledgeDirectory.scope == scope,
    )
    if scope == "personal":
        dir_stmt = dir_stmt.where(KnowledgeDirectory.user_id == user_id)
    else:
        dir_stmt = dir_stmt.where(KnowledgeDirectory.user_id.is_(None))
    directory = (await db.execute(dir_stmt)).scalar_one_or_none()
    if directory is None:
        raise ValueError("目录不存在或无权访问")

    try:
        file_parser.validate_file_signature(file_bytes, file_ext)
        await run_in_threadpool(virus_scan.scan_bytes, file_bytes)
        content_text = await run_in_threadpool(file_parser.parse_file, file_bytes, filename)
    except Exception as exc:
        logger.warning("Failed to parse knowledge document %s: %s", filename, exc)
        raise ValueError(f"文件解析失败：{exc}") from exc
    if not content_text or not content_text.strip():
        raise ValueError("未能从文件中解析出文本内容")

    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    try:
        storage_path = await run_in_threadpool(
            file_storage.upload_file, file_bytes, filename, content_type
        )
    except Exception as exc:
        logger.error("Failed to store knowledge document %s: %s", filename, exc)
        raise ValueError("文件存储失败，请检查 MinIO 配置") from exc

    doc = KnowledgeDocument(
        directory_id=directory_id, scope=scope,
        user_id=user_id if scope == "personal" else None,
        title=title, file_type=file_ext, storage_path=storage_path,
        content_text=content_text, status="draft",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    try:
        await _index_document(db, doc)
    except Exception:
        # Do not leave a document that references a directory but has no
        # usable index (e.g. embedding dimension mismatch).
        await db.delete(doc)
        await db.commit()
        raise
    return doc


async def list_documents(
    db: AsyncSession, user_id: uuid.UUID | None, scope: str,
    directory_id: uuid.UUID | None = None, skip: int = 0, limit: int = 20,
) -> tuple[list[KnowledgeDocument], int]:
    stmt = select(KnowledgeDocument).where(KnowledgeDocument.scope == scope)
    if scope == "personal" and user_id:
        stmt = stmt.where(KnowledgeDocument.user_id == user_id)
    elif scope == "global":
        stmt = stmt.where(KnowledgeDocument.user_id.is_(None))
    if directory_id:
        stmt = stmt.where(KnowledgeDocument.directory_id == directory_id)

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(stmt.order_by(KnowledgeDocument.created_at.desc()).offset(skip).limit(limit))
    return list(result.scalars().all()), total


async def get_document(db: AsyncSession, doc_id: uuid.UUID, user_id: uuid.UUID | None, scope: str) -> KnowledgeDocument | None:
    stmt = select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id, KnowledgeDocument.scope == scope)
    if scope == "personal" and user_id:
        stmt = stmt.where(KnowledgeDocument.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_document(db: AsyncSession, doc_id: uuid.UUID, user_id: uuid.UUID | None, scope: str, data: DocumentUpdate) -> KnowledgeDocument | None:
    doc = await get_document(db, doc_id, user_id, scope)
    if doc is None:
        return None
    updates = data.model_dump(exclude_unset=True)
    content_changed = "content_text" in updates and updates["content_text"] != doc.content_text
    for key, value in updates.items():
        setattr(doc, key, value)

    if not content_changed:
        await db.commit()
        await db.refresh(doc)
        return doc

    if scope == "global":
        # Keep serving the published snapshot until the admin publishes again.
        doc.status = "draft"
        await db.commit()
        await db.refresh(doc)
        return doc

    await db.commit()
    await db.refresh(doc)
    await _index_document(db, doc)
    return doc


async def delete_document(db: AsyncSession, doc_id: uuid.UUID, user_id: uuid.UUID | None, scope: str) -> bool:
    doc = await get_document(db, doc_id, user_id, scope)
    if doc is None:
        return False
    collection = _collection_name(scope, user_id)
    storage_path = doc.storage_path
    try:
        await run_in_threadpool(vector_store.delete_by_document, collection, str(doc.id))
    except Exception:
        pass
    chunks_result = await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id))
    for chunk in chunks_result.scalars().all():
        await db.delete(chunk)
    await db.delete(doc)
    await db.commit()
    try:
        await run_in_threadpool(file_storage.delete_file, storage_path)
    except Exception:
        logger.warning("Failed to delete knowledge file %s", storage_path, exc_info=True)
    return True


async def reindex_document(db: AsyncSession, doc_id: uuid.UUID, user_id: uuid.UUID | None, scope: str) -> KnowledgeDocument | None:
    doc = await get_document(db, doc_id, user_id, scope)
    if doc is None:
        return None
    await _index_document(db, doc)
    return doc


async def search_knowledge(db: AsyncSession, user_id: uuid.UUID, query: str, scope: str = "personal", top_k: int = 10) -> list[dict]:
    collection = _collection_name(scope, user_id if scope == "personal" else None)
    if not await run_in_threadpool(vector_store.collection_exists, collection):
        return []

    try:
        query_vector = await get_embedding(query)
    except Exception as exc:
        logger.error("Embedding query failed for collection %s: %s", collection, exc)
        raise KnowledgeSearchError("知识库检索失败：Embedding 服务不可用，请检查模型配置") from exc

    try:
        results = await run_in_threadpool(
            vector_store.search, collection, query_vector, max(top_k * 2, top_k)
        )
    except Exception as exc:
        logger.error("Vector search failed for collection %s: %s", collection, exc)
        raise KnowledgeSearchError("知识库检索失败：向量库不可用") from exc

    doc_ids: set[uuid.UUID] = set()
    for result in results:
        raw_id = result.get("payload", {}).get("document_id")
        if raw_id:
            try:
                doc_ids.add(uuid.UUID(raw_id))
            except (ValueError, TypeError):
                continue

    titles: dict[str, str] = {}
    if doc_ids:
        rows = await db.execute(
            select(KnowledgeDocument.id, KnowledgeDocument.title).where(KnowledgeDocument.id.in_(doc_ids))
        )
        titles = {str(row[0]): row[1] for row in rows.all()}

    search_results = []
    for result in results:
        payload = result.get("payload", {})
        text = payload.get("text", "")
        base_score = float(result.get("score", 0.0))
        keyword_score = _keyword_overlap(query, text)

        boost = 1.15 if payload.get("is_high_score") else 1.0
        case_score = float(payload.get("case_score") or 0)
        boost *= 1.0 + min(case_score, 100) / 1000

        # Lightweight hybrid score: vector similarity plus keyword overlap.
        score = min(1.0, base_score * 0.8 * boost + keyword_score * 0.2)
        doc_id_str = payload.get("document_id")
        search_results.append({
            "chunk_text": text,
            "document_id": doc_id_str,
            "document_title": titles.get(doc_id_str, ""),
            "score": score,
            "metadata": payload.get("metadata", {}),
        })

    search_results.sort(key=lambda item: item["score"], reverse=True)
    return search_results[:top_k]


async def search_for_generation(
    db: AsyncSession, user_id: uuid.UUID, query: str, top_k: int = 6
) -> list[dict]:
    """Retrieve personal + global chunks for a writing agent.

    Global knowledge is readable by every user; personal knowledge is scoped by
    the collection name. Results are de-duplicated by document/chunk prefix.
    """
    personal = await search_knowledge(db, user_id, query, "personal", top_k)
    shared = await search_knowledge(db, user_id, query, "global", top_k)

    merged: dict[tuple[str | None, str], dict] = {}
    for item in [*personal, *shared]:
        key = (item.get("document_id"), item.get("chunk_text", "")[:80])
        existing = merged.get(key)
        if existing is None or item.get("score", 0) > existing.get("score", 0):
            merged[key] = item

    return sorted(merged.values(), key=lambda item: item.get("score", 0), reverse=True)[:top_k]


async def publish_document(db: AsyncSession, doc_id: uuid.UUID) -> KnowledgeDocument | None:
    stmt = select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id, KnowledgeDocument.scope == "global")
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if doc is None:
        return None
    doc.status = "published"
    doc.published_content_text = doc.content_text
    doc.published_at = datetime.now(timezone.utc)
    await db.commit()
    await _index_document(db, doc)
    return doc


async def _index_document(db: AsyncSession, doc: KnowledgeDocument) -> None:
    collection = _collection_name(doc.scope, doc.user_id)

    if doc.scope == "global":
        index_text = doc.published_content_text if doc.status == "published" else None
        if index_text is None and doc.status == "published":
            # Legacy rows published before the snapshot column existed.
            index_text = doc.content_text
    else:
        index_text = doc.content_text

    old_chunks = await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id))
    for old in old_chunks.scalars().all():
        await db.delete(old)
    try:
        await run_in_threadpool(vector_store.delete_by_document, collection, str(doc.id))
    except Exception:
        pass

    if not index_text:
        doc.vector_collection_id = None
        await db.commit()
        return

    texts = _split_text(index_text)
    try:
        vectors_list = await get_embeddings_batch(texts)
    except Exception as exc:
        logger.error("Embedding failed for document %s: %s", doc.id, exc)
        doc.vector_collection_id = None
        await db.commit()
        return

    if not vectors_list or len(vectors_list) != len(texts):
        raise ValueError("Embedding 返回数量与文本分块数量不一致")
    dims = {len(vector) for vector in vectors_list}
    if len(dims) != 1:
        raise ValueError("Embedding 返回的向量维度不一致")
    vector_dim = dims.pop()
    await run_in_threadpool(vector_store.ensure_collection, collection, vector_dim)

    chunks_to_upsert = []
    for i, text in enumerate(texts):
        chunk_id = uuid.uuid4()
        chunk = KnowledgeChunk(
            id=chunk_id, document_id=doc.id, chunk_index=i, text=text,
            metadata_={"source": doc.title, "file_type": doc.file_type},
        )
        db.add(chunk)
        chunks_to_upsert.append({
            "id": str(chunk_id), "vector": vectors_list[i],
            "payload": {
                "text": text,
                "document_id": str(doc.id),
                "chunk_index": i,
                "status": doc.status,
                "case_score": doc.case_score,
                "is_high_score": doc.is_high_score,
                "metadata": {"source": doc.title},
            },
        })
    await db.flush()
    await run_in_threadpool(vector_store.upsert_chunks, collection, chunks_to_upsert)
    doc.vector_collection_id = collection
    await db.commit()
    await db.refresh(doc)
