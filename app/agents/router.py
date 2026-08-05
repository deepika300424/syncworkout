from __future__ import annotations

from typing import Literal


Intent = Literal["search", "media_action", "navigation", "fallback"]


def detect_intent(query: str) -> Intent:
    text = query.lower()
    if any(keyword in text for keyword in ("play", "show video", "intro", "preview", "audio")):
        return "media_action"
    if any(keyword in text for keyword in ("next", "previous", "skip", "go to section")):
        return "navigation"
    if any(keyword in text for keyword in ("find", "search", "workout", "exercise", "section")):
        return "search"
    return "fallback"

