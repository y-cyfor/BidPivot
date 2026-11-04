from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from app.config import settings

client = QdrantClient(url=settings.QDRANT_URL)

DEFAULT_VECTOR_DIM = 768


def _existing_dim(info) -> int | None:
    vectors = info.config.params.vectors
    if hasattr(vectors, "size"):
        return vectors.size
    if isinstance(vectors, dict) and vectors:
        return next(iter(vectors.values())).size
    return None


def ensure_collection(collection_name: str, vector_dim: int) -> None:
    """Create the collection with the model's real dimension.

    Silently creating a 768-dim collection and then upserting 1024/1536-dim
    vectors makes every write fail. Reject mismatches with a clear error.
    """
    if vector_dim <= 0:
        raise ValueError("向量维度无效")

    collections = [c.name for c in client.get_collections().collections]
    if collection_name not in collections:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE),
        )
        return

    existing = _existing_dim(client.get_collection(collection_name))
    if existing is not None and existing != vector_dim:
        raise ValueError(
            f"向量集合 {collection_name} 现有维度 {existing}，与当前 Embedding 维度 {vector_dim} 不一致；"
            "请更换集合或在设置中改用相同维度的模型"
        )


def upsert_chunks(collection_name: str, chunks: list[dict]) -> None:
    points = [
        PointStruct(id=str(c["id"]), vector=c["vector"], payload=c["payload"])
        for c in chunks
    ]
    client.upsert(collection_name=collection_name, points=points)


def search(collection_name: str, query_vector: list[float], top_k: int = 10) -> list[dict]:
    results = client.search(collection_name=collection_name, query_vector=query_vector, limit=top_k)
    return [{"id": r.id, "score": r.score, "payload": r.payload} for r in results]


def delete_by_document(collection_name: str, document_id: str) -> None:
    client.delete(
        collection_name=collection_name,
        points_selector=Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]),
    )


def delete_collection(collection_name: str) -> None:
    collections = [c.name for c in client.get_collections().collections]
    if collection_name in collections:
        client.delete_collection(collection_name)


def collection_exists(collection_name: str) -> bool:
    return collection_name in [c.name for c in client.get_collections().collections]
