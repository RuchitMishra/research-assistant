import hashlib
import os
import tempfile
import uuid
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.ingestion.loaders import LOADERS
from app.schemas import DocumentInfo
from app.vectorstore.store import add_chunks, doc_exists


def ingest_file(filename: str, data: bytes) -> DocumentInfo:
    """Single ingestion path for every supported format."""
    s = get_settings()
    ext = Path(filename).suffix.lower()

    if ext not in LOADERS:
        raise ValueError(f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(LOADERS))}")
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise ValueError(f"File exceeds {s.max_upload_mb} MB limit.")
    if not data:
        raise ValueError("File is empty.")

    file_hash = hashlib.sha256(data).hexdigest()
    doc_id = file_hash[:16]
    if doc_exists(doc_id):
        return DocumentInfo(doc_id=doc_id, filename=filename, chunks=0, status="duplicate (already ingested)")

    # loaders work on paths, so spill to a temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    try:
        tmp.write(data)
        tmp.close()
        raw_docs = LOADERS[ext](Path(tmp.name))
    finally:
        os.unlink(tmp.name)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=s.chunk_size, chunk_overlap=s.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(raw_docs)
    if not chunks:
        raise ValueError("No text could be extracted.")

    ids = []
    for i, c in enumerate(chunks):
        c.metadata = {
            "doc_id": doc_id,
            "filename": filename,
            "file_hash": file_hash,
            "file_type": ext.lstrip("."),
            "page": c.metadata.get("page"),
            "section": c.metadata.get("section"),
            "chunk_index": i,
        }
        ids.append(str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}-{i}")))

    add_chunks(chunks, ids)
    return DocumentInfo(doc_id=doc_id, filename=filename, chunks=len(chunks))
