from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from app.agents.render_payload_agent import build_render_payload
from app.agents.response_agent import generate_grounded_response
from app.agents.retrieval_agent import retrieve_context
from app.agents.router import detect_intent
from app.core.schemas import RenderPayload, RetrievedItem
from app.index.hybrid_index import HybridRetriever


class GraphState(TypedDict):
    query: str
    intent: str
    retrieved_items: list[RetrievedItem]
    answer: str
    render_payload: RenderPayload


def build_workflow(
    retriever: HybridRetriever,
    llm: BaseChatModel,
    faiss_top_k: int,
    bm25_top_k: int,
):
    graph = StateGraph(GraphState)

    def route_node(state: GraphState) -> dict[str, Any]:
        return {"intent": detect_intent(state["query"])}

    def retrieval_node(state: GraphState) -> dict[str, Any]:
        items = retrieve_context(
            retriever=retriever,
            query=state["query"],
            faiss_top_k=faiss_top_k,
            bm25_top_k=bm25_top_k,
        )
        return {"retrieved_items": items}

    def response_node(state: GraphState) -> dict[str, Any]:
        answer = generate_grounded_response(
            llm=llm,
            query=state["query"],
            intent=state["intent"],
            retrieved_items=state["retrieved_items"],
        )
        return {"answer": answer}

    def render_payload_node(state: GraphState) -> dict[str, Any]:
        payload = build_render_payload(
            query=state["query"],
            intent=state["intent"],
            retrieved_items=state["retrieved_items"],
        )
        return {"render_payload": payload}

    graph.add_node("route", route_node)
    graph.add_node("retrieve", retrieval_node)
    graph.add_node("respond", response_node)
    graph.add_node("render_payload", render_payload_node)

    graph.add_edge(START, "route")
    graph.add_edge("route", "retrieve")
    graph.add_edge("retrieve", "respond")
    graph.add_edge("respond", "render_payload")
    graph.add_edge("render_payload", END)

    return graph.compile()
