from functools import lru_cache
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (clarify_node, grade_node, plan_node, retrieve_node,
                             route_after_grade, route_after_plan, synthesize_node, web_node)
from app.graph.state import GraphState


@lru_cache
def get_graph():
    g = StateGraph(GraphState)
    g.add_node("plan", plan_node)
    g.add_node("clarify", clarify_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("grade", grade_node)
    g.add_node("web_search", web_node)
    g.add_node("synthesize", synthesize_node)

    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", route_after_plan, {"clarify": "clarify", "retrieve": "retrieve"})
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", route_after_grade,
                            {"retrieve": "retrieve", "web_search": "web_search", "synthesize": "synthesize"})
    g.add_edge("web_search", "synthesize")
    g.add_edge("clarify", END)
    g.add_edge("synthesize", END)
    return g.compile(checkpointer=MemorySaver())  # memory keyed by thread_id (= session_id)
