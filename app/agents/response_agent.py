from __future__ import annotations

import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.schemas import RetrievedItem


def generate_grounded_response(
    llm: BaseChatModel,
    query: str,
    intent: str,
    retrieved_items: list[RetrievedItem],
) -> str:
    context_payload = [item.model_dump() for item in retrieved_items[:8]]
    system_prompt = (
        "You are a workout recommendation assistant for end users. "
        "Use only the retrieved context. "
        "Never output raw JSON, signatures, chunk IDs, scores, metadata keys, or internal paths unless explicitly asked. "
        "Write a clear, polished response that is easy for a user to understand. "
        "When possible, suggest 1-3 best matches and explain briefly why each matches the query. "
        "If useful, mention that intro video, cover image, or exercise media is available without dumping technical details. "
        "If context is insufficient, say that the requested information was not found in the dataset."
    )
    user_prompt = (
        f"Intent: {intent}\n"
        f"User query: {query}\n"
        "Return style:\n"
        "- Start with a direct answer in one sentence.\n"
        "- Then provide short bullet points for recommendations.\n"
        "- Keep the tone motivating and concise.\n\n"
        f"Retrieved context (JSON):\n{json.dumps(context_payload, indent=2)}"
    )
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
    if isinstance(response.content, str):
        return response.content
    if isinstance(response.content, list):
        text_blocks = [
            block.get("text", "")
            for block in response.content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "\n\n".join(text for text in text_blocks if text).strip()
    return str(response.content)
