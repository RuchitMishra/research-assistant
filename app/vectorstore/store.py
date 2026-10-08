import time
from functools import lru_cache

from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models

from app.core.config import get_settings

_collection_ready = False


@lru_cache
def get_client() -> QdrantClient:
    s = get_settings()
    return QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key, timeout=60)


@lru_cache
def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    s = get_settings()
    name = s.embedding_model
    if not name.startswith("models/"):
        name = f"models/{name}"
    return GoogleGenerativeAIEmbeddings(model=name, google_api_key=s.google_api_key)


def ensure_collection() -> None:
    """Create the collection (and filter indexes) once. Vector size is probed, not hardcoded."""
    global _collection_ready
    if _collection_ready:
        return
    s = get_settings()
    client = get_client()
    if not client.collection_exists(s.qdrant_collection):
        dim = len(get_embeddings().embed_query("dimension probe"))
        client.create_collection(
            collection_name=s.qdrant_collection,
            vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
        )
    for field in ("metadata.doc_id", "metadata.file_hash"):
        try:
            client.create_payload_index(
                s.qdrant_collection, field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass  # already exists
    _collection_ready = True


def get_vectorstore() -> QdrantVectorStore:
    ensure_collection()
    return QdrantVectorStore(
        client=get_client(),
        collection_name=get_settings().qdrant_collection,
        embedding=get_embeddings(),
    )


def _doc_filter(doc_id: str) -> models.Filter:
    return models.Filter(must=[
        models.FieldCondition(key="metadata.doc_id", match=models.MatchValue(value=doc_id))
    ])


def doc_exists(doc_id: str) -> bool:
    ensure_collection()
    res = get_client().count(
        get_settings().qdrant_collection, count_filter=_doc_filter(doc_id), exact=True
    )
    return res.count > 0


def add_chunks(docs: list[Document], ids: list[str]) -> None:
    """Embed + upsert in small batches with backoff (free-tier rate limits)."""
    vs = get_vectorstore()
    batch = 32
    for i in range(0, len(docs), batch):
        for attempt in range(5):
            try:
                vs.add_documents(docs[i:i + batch], ids=ids[i:i + batch])
                break
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(3 * (2 ** attempt))
        time.sleep(0.5)


def list_documents() -> list[dict]:
    ensure_collection()
    client = get_client()
    name = get_settings().qdrant_collection
    docs: dict[str, dict] = {}
    offset = None
    while True:
        points, offset = client.scroll(
            name, limit=256, offset=offset, with_payload=["metadata"], with_vectors=False
        )
        for p in points:
            m = (p.payload or {}).get("metadata", {})
            d = docs.setdefault(
                m.get("doc_id"),
                {"doc_id": m.get("doc_id"), "filename": m.get("filename"), "chunks": 0},
            )
            d["chunks"] += 1
        if offset is None:
            break
    return list(docs.values())


def delete_document(doc_id: str) -> int:
    ensure_collection()
    client = get_client()
    name = get_settings().qdrant_collection
    n = client.count(name, count_filter=_doc_filter(doc_id), exact=True).count
    if n:
        client.delete(name, points_selector=models.FilterSelector(filter=_doc_filter(doc_id)))
    return n
