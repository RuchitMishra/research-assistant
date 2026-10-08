from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.llm import get_llm
from app.schemas import AskRequest, AskResponse
from app.vectorstore.store import get_vectorstore

router = APIRouter()
STATIC = Path(__file__).resolve().parent.parent / "static"


@router.get("/ui", include_in_schema=False)
def ui():
    return FileResponse(STATIC / "index.html")


@router.post("/ask-naive", response_model=AskResponse, tags=["ask"])
def ask_naive(req: AskRequest):
    """BASELINE for comparison: one retrieval + one generation. No planning, grading, memory or web fallback."""
    try:
        hits = get_vectorstore().similarity_search_with_score(req.question, k=get_settings().top_k)
        ctx = "\n\n".join(f"[{d.metadata.get('filename')} p.{d.metadata.get('page')}] {d.page_content}" for d, _ in hits)
        r = get_llm().invoke(f"Answer the question using the context.\n\nContext:\n{ctx}\n\nQuestion: {req.question}")
    except Exception as e:
        raise HTTPException(502, f"Naive pipeline failed: {e}")
    c = r.content
    answer = c if isinstance(c, str) else "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
    cites = [{"doc": d.metadata.get("filename"), "page": d.metadata.get("page"),
              "snippet": d.page_content[:300], "score": round(float(s), 3)} for d, s in hits]
    return AskResponse(answer=answer, answer_source="knowledge_base", citations=cites,
                       reasoning_trace=["naive: 1 retrieve + 1 generate (no grading, no web fallback, no memory)"],
                       session_id=req.session_id)
