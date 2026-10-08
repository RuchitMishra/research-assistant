from langchain_core.messages import AIMessage
from langchain_tavily import TavilySearch
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.llm import get_llm
from app.graph.state import GraphState
from app.vectorstore.store import get_vectorstore, list_documents


# ---------- structured outputs ----------
class QueryPlan(BaseModel):
    standalone_question: str = Field(description="Question rewritten to be fully self-contained using chat history")
    is_ambiguous: bool = Field(description="True ONLY if it cannot be answered sensibly without asking the user something")
    clarifying_question: str = Field(default="", description="Question to ask the user if ambiguous, else empty")
    sub_questions: list[str] = Field(description="1 item if simple; 2-4 independent search queries if compound/comparative")


class Grade(BaseModel):
    sufficient: bool = Field(description="True only if the evidence fully answers the question")
    missing: str = Field(default="", description="What information is missing")
    better_queries: list[str] = Field(default=[], description="1-3 improved search queries to find the missing info")


class Synth(BaseModel):
    answer: str
    used_sources: list[str] = Field(description="IDs like KB1, W2 of sources actually used in the answer")


def _history(state: GraphState, n: int = 6) -> str:
    msgs = state["messages"][:-1][-n:]  # exclude current question
    return "\n".join(f"{'User' if m.type == 'human' else 'Assistant'}: {m.content}" for m in msgs) or "(none)"


def _t(state: GraphState, msg: str) -> list[str]:
    return state.get("trace", []) + [msg]


# ---------- nodes ----------
def plan_node(state: GraphState) -> dict:
    files = sorted({d["filename"] for d in list_documents()}) or ["(empty)"]
    prompt = f"""You plan retrieval for a document Q&A system.
Knowledge base files: {files}
Chat history:
{_history(state)}
Latest user question: {state['question']}

1. Rewrite it as a standalone question (resolve pronouns/follow-ups like "and for 2023?" from history).
2. Mark ambiguous ONLY if it is genuinely under-specified (e.g. "tell me about it" with no history). If a reasonable interpretation exists, do NOT ask; just answer.
3. If compound or comparative, split into independent sub-questions (max 4), each self-contained. Otherwise one sub-question."""
    plan = get_llm().with_structured_output(QueryPlan).invoke(prompt)
    subs = [q for q in plan.sub_questions if q.strip()] or [plan.standalone_question]
    return {
        "standalone_question": plan.standalone_question,
        "is_ambiguous": plan.is_ambiguous and bool(plan.clarifying_question.strip()),
        "clarifying_question": plan.clarifying_question,
        "sub_questions": subs,
        "trace": _t(state, f"plan: standalone='{plan.standalone_question}' | {len(subs)} sub-question(s) | ambiguous={plan.is_ambiguous}"),
    }


def clarify_node(state: GraphState) -> dict:
    return {
        "answer": state["clarifying_question"],
        "answer_source": "clarification_needed",
        "citations": [], "web_sources": [],
        "messages": [AIMessage(content=state["clarifying_question"])],
        "trace": _t(state, "route: ambiguous -> asking clarifying question"),
    }


def retrieve_node(state: GraphState) -> dict:
    s = get_settings()
    retry = state.get("retry_count", 0)
    queries = state["sub_questions"] if retry == 0 else (state.get("better_queries") or state["sub_questions"])
    vs = get_vectorstore()
    found = {(d["doc_id"], d["chunk_index"]): d for d in state.get("docs", [])}
    for q in queries:
        for doc, score in vs.similarity_search_with_score(q, k=s.top_k):
            m = doc.metadata
            key = (m.get("doc_id"), m.get("chunk_index"))
            if key not in found or score > found[key]["score"]:
                found[key] = {"text": doc.page_content, "filename": m.get("filename"), "page": m.get("page"),
                              "doc_id": m.get("doc_id"), "chunk_index": m.get("chunk_index"), "score": float(score)}
    docs = sorted(found.values(), key=lambda d: d["score"], reverse=True)
    return {"docs": docs, "trace": _t(state, f"retrieve (attempt {retry + 1}): {len(queries)} query(ies) -> {len(docs)} unique chunks")}


def grade_node(state: GraphState) -> dict:
    s = get_settings()
    docs = state.get("docs", [])
    if not docs:
        return {"retry_count": s.max_retries + 1, "trace": _t(state, "grade: knowledge base empty -> web fallback")}
    ctx = "\n\n".join(f"[{d['filename']} p.{d['page']}] {d['text'][:600]}" for d in docs[:8])
    prompt = f"""Judge whether the evidence is enough to FULLY answer the question. Be strict: if any part
(e.g. one side of a comparison, a specific number, a date) is missing, mark insufficient.
Question: {state['standalone_question']}
Sub-questions: {state['sub_questions']}
Evidence:
{ctx}"""
    g = get_llm().with_structured_output(Grade).invoke(prompt)
    if g.sufficient:
        return {"trace": _t(state, "grade: sufficient")}
    return {
        "better_queries": g.better_queries,
        "retry_count": state.get("retry_count", 0) + 1,
        "trace": _t(state, f"grade: insufficient (missing: {g.missing})"),
    }


def web_node(state: GraphState) -> dict:
    s = get_settings()
    try:
        res = TavilySearch(max_results=4, tavily_api_key=s.tavily_api_key).invoke({"query": state["standalone_question"]})
        results = [{"url": r.get("url", ""), "title": r.get("title", ""), "content": r.get("content", "")}
                   for r in (res.get("results", []) if isinstance(res, dict) else [])]
    except Exception as e:
        results = []
        return {"web_results": results, "trace": _t(state, f"web search failed: {e}")}
    return {"web_results": results, "trace": _t(state, f"web search: {len(results)} result(s)")}


def synthesize_node(state: GraphState) -> dict:
    docs = state.get("docs", [])[:8]
    web = state.get("web_results", [])
    if not docs and not web:
        msg = "I couldn't find this in the knowledge base or on the web."
        return {"answer": msg, "answer_source": "not_found", "citations": [], "web_sources": [],
                "messages": [AIMessage(content=msg)], "trace": _t(state, "synthesize: no evidence -> not_found")}

    parts = [f"[KB{i}] ({d['filename']}, page {d['page']}): {d['text']}" for i, d in enumerate(docs, 1)]
    parts += [f"[W{i}] ({w['title']} - {w['url']}): {w['content']}" for i, w in enumerate(web, 1)]
    prompt = f"""Answer using ONLY the sources below. Never use outside knowledge.
- Answer every part of the question that the sources support; for parts they don't support, say clearly what is not found.
- If the sources don't contain the answer at all, say so and list no used_sources.
- Mention which file or website each key fact came from. Be concise.
- used_sources: IDs (e.g. KB1, W2) of sources you actually relied on.

Chat history:
{_history(state)}
Question: {state['standalone_question']}

Sources:
{chr(10).join(parts)}"""
    out = get_llm().with_structured_output(Synth).invoke(prompt)

    used = set(out.used_sources)
    cites = [{"doc": d["filename"], "page": d["page"], "snippet": d["text"][:300], "score": round(d["score"], 3)}
             for i, d in enumerate(docs, 1) if f"KB{i}" in used]
    wsrc = [{"url": w["url"], "title": w["title"]} for i, w in enumerate(web, 1) if f"W{i}" in used]
    source = ("mixed" if cites and wsrc else "knowledge_base" if cites else "web" if wsrc else "not_found")
    return {"answer": out.answer, "answer_source": source, "citations": cites, "web_sources": wsrc,
            "messages": [AIMessage(content=out.answer)],
            "trace": _t(state, f"synthesize: used {len(cites)} KB source(s), {len(wsrc)} web source(s) -> {source}")}


# ---------- routing ----------
def route_after_plan(state: GraphState) -> str:
    return "clarify" if state.get("is_ambiguous") else "retrieve"


def route_after_grade(state: GraphState) -> str:
    s = get_settings()
    last = state["trace"][-1]
    if last.startswith("grade: sufficient"):
        return "synthesize"
    return "retrieve" if state.get("retry_count", 0) <= s.max_retries else "web_search"
