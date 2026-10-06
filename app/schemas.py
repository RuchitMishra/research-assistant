from typing import Literal, Optional
from pydantic import BaseModel, Field


class Citation(BaseModel):
    doc: str
    page: Optional[int] = None
    snippet: str
    score: Optional[float] = None


class WebSource(BaseModel):
    url: str
    title: str = ""


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    session_id: str = "default"


class AskResponse(BaseModel):
    answer: str
    answer_source: Literal[
        "knowledge_base", "web", "mixed", "clarification_needed", "not_found"
    ]
    citations: list[Citation] = []
    web_sources: list[WebSource] = []
    reasoning_trace: list[str] = []
    session_id: str


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    chunks: int
    status: str = "ingested"
