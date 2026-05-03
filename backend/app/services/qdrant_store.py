from typing import Any

from ..config import settings

_QDRANT_CLIENT = None


def get_qdrant_client():
    global _QDRANT_CLIENT
    if _QDRANT_CLIENT is not None:
        return _QDRANT_CLIENT
    try:
        from qdrant_client import QdrantClient
    except Exception:
        return None
    if not settings.qdrant_url:
        return None
    try:
        _QDRANT_CLIENT = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    except Exception:
        return None
    return _QDRANT_CLIENT


def ensure_collection(vector_size: int) -> None:
    client = get_qdrant_client()
    if client is None:
        return
    try:
        from qdrant_client.models import Distance, VectorParams
        collections = {item.name for item in client.get_collections().collections}
        if settings.qdrant_collection_name not in collections:
            client.create_collection(
                collection_name=settings.qdrant_collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
    except Exception:
        return


def upsert_case_vector(case_id: int, vector: list[float], payload: dict[str, Any]) -> None:
    client = get_qdrant_client()
    if client is None or not vector:
        return
    try:
        from qdrant_client.models import PointStruct

        ensure_collection(len(vector))
        client.upsert(
            collection_name=settings.qdrant_collection_name,
            points=[PointStruct(id=case_id, vector=vector, payload=payload)],
        )
    except Exception:
        return


def search_case_vectors(query_vector: list[float], limit: int, org_id: int | None = None) -> list[dict[str, Any]]:
    client = get_qdrant_client()
    if client is None or not query_vector:
        return []
    try:
        query_filter = None
        if org_id is not None:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            query_filter = Filter(must=[FieldCondition(key="org_id", match=MatchValue(value=org_id))])
        hits = client.search(
            collection_name=settings.qdrant_collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=query_filter,
        )
    except Exception:
        return []
    results = []
    for hit in hits:
        payload = dict(hit.payload or {})
        payload["id"] = hit.id
        payload["vector_score"] = float(hit.score)
        results.append(payload)
    return results
