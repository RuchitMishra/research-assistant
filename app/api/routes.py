from fastapi import APIRouter, File, HTTPException, UploadFile

from app.ingestion.pipeline import ingest_file
from app.schemas import DocumentInfo
from app.vectorstore.store import delete_document, list_documents

router = APIRouter(tags=["documents"])


# Plain `def` endpoints run in FastAPI's threadpool, so slow embedding calls don't block the server.
@router.post("/documents", response_model=list[DocumentInfo])
def upload_documents(files: list[UploadFile] = File(...)):
    results = []
    for f in files:
        try:
            results.append(ingest_file(f.filename or "unknown", f.file.read()))
        except Exception as e:
            results.append(DocumentInfo(doc_id="", filename=f.filename or "unknown",
                                        chunks=0, status=f"failed: {e}"))
    return results


@router.get("/documents")
def get_documents():
    return list_documents()


@router.delete("/documents/{doc_id}")
def remove_document(doc_id: str):
    n = delete_document(doc_id)
    if n == 0:
        raise HTTPException(404, "Document not found")
    return {"deleted_chunks": n, "doc_id": doc_id}
