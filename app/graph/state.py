from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages


class GraphState(TypedDict, total=False):
    messages: Annotated[list, add_messages]   # conversation memory (per thread_id)
    question: str
    standalone_question: str
    is_ambiguous: bool
    clarifying_question: str
    sub_questions: list[str]
    better_queries: list[str]
    docs: list[dict]          # retrieved KB chunks
    retry_count: int
    web_results: list[dict]
    answer: str
    answer_source: str
    citations: list[dict]
    web_sources: list[dict]
    trace: list[str]
