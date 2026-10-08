from fastapi import APIRouter, File, HTTPException, UploadFile
from langchain_core.messages import HumanMessage

from app.graph.builder import get_graph
from app.ingestion.pipeline import ingest_file
from app.schemas import AskRequest, AskResponse, DocumentInfo
from app.vectorstore.store import delete_document, list_documents

router = APIRouter()


# Plain `def` endpoints run in FastAPI's threadpool, so slow LLM/embedding calls don't block the server.
@router.post("/documents", response_model=list[DocumentInfo], tags=["documents"])
def upload_documents(files: list[UploadFile] = File(...)):
    results = []
    for f in files:
        try:
            results.append(ingest_file(f.filename or "unknown", f.file.read()))
        except Exception as e:
            results.append(DocumentInfo(doc_id="", filename=f.filename or "unknown",
                                        chunks=0, status=f"failed: {e}"))
    return results


@router.get("/documents", tags=["documents"])
def get_documents():
    return list_documents()


@router.delete("/documents/{doc_id}", tags=["documents"])
def remove_document(doc_id: str):
    n = delete_document(doc_id)
    if n == 0:
        raise HTTPException(404, "Document not found")
    return {"deleted_chunks": n, "doc_id": doc_id}


@router.post("/ask", response_model=AskResponse, tags=["ask"])
def ask(req: AskRequest):
    init = {
        "messages": [HumanMessage(content=req.question)],
        "question": req.question,
        # per-turn state must be reset because the checkpointer persists it across turns
        "docs": [], "web_results": [], "better_queries": [], "sub_questions": [],
        "retry_count": 0, "trace": [],
    }
    try:
        out = get_graph().invoke(init, config={"configurable": {"thread_id": req.session_id}})
    except Exception as e:
        raise HTTPException(502, f"Agent failed (possibly LLM rate limit, retry in a minute): {e}")
    return AskResponse(
        answer=out["answer"], answer_source=out["answer_source"],
        citations=out.get("citations", []), web_sources=out.get("web_sources", []),
        reasoning_trace=out.get("trace", []), session_id=req.session_id,
    )
