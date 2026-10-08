"""One loader per file type. Every loader returns list[Document] with `page` metadata where relevant."""
import base64
from pathlib import Path

from bs4 import BeautifulSoup
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

from app.core.llm import get_llm


def load_pdf(path: Path) -> list[Document]:
    pages = PyPDFLoader(str(path)).load()
    out = [
        Document(page_content=p.page_content, metadata={"page": int(p.metadata.get("page", 0)) + 1})
        for p in pages if p.page_content.strip()
    ]
    if not out:
        raise ValueError("PDF has no extractable text (scanned?). Upload pages as images for OCR.")
    return out


def load_docx(path: Path) -> list[Document]:
    return Docx2txtLoader(str(path)).load()


def load_html(path: Path) -> list[Document]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "footer"]):
        tag.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    text = soup.get_text("\n")
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return [Document(page_content=text, metadata={"section": title})]


def load_text(path: Path) -> list[Document]:
    return [Document(page_content=path.read_text(encoding="utf-8", errors="ignore"))]


_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def load_image(path: Path) -> list[Document]:
    """OCR via Gemini vision (free tier) - no Tesseract install needed."""
    b64 = base64.b64encode(path.read_bytes()).decode()
    msg = HumanMessage(content=[
        {"type": "text", "text": "Transcribe ALL text in this image exactly. Keep tables as plain text rows. Output only the transcription."},
        {"type": "image_url", "image_url": f"data:{_MIME[path.suffix.lower()]};base64,{b64}"},
    ])
    text = get_llm().invoke([msg]).content
    if not isinstance(text, str):
        text = str(text)
    if not text.strip():
        raise ValueError("OCR returned no text.")
    return [Document(page_content=text, metadata={"section": "ocr"})]


LOADERS = {
    ".pdf": load_pdf,
    ".docx": load_docx,
    ".html": load_html,
    ".htm": load_html,
    ".txt": load_text,
    ".md": load_text,
    ".png": load_image,
    ".jpg": load_image,
    ".jpeg": load_image,
    ".webp": load_image,
}
