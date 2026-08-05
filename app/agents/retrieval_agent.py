from __future__ import annotations

from app.core.schemas import RetrievedItem
from app.index.hybrid_index import HybridRetriever


def retrieve_context(
    retriever: HybridRetriever,
    query: str,
    faiss_top_k: int,
    bm25_top_k: int,
) -> list[RetrievedItem]:
    return retriever.search(query=query, faiss_top_k=faiss_top_k, bm25_top_k=bm25_top_k)

