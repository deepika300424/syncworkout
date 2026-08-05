from __future__ import annotations

import json
from urllib import error, request

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.settings import Settings


def _check_ollama_availability(settings: Settings) -> str:
    base_url = settings.ollama_base_url.rstrip("/")
    endpoint = f"{base_url}/api/tags"
    try:
        with request.urlopen(endpoint, timeout=settings.ollama_request_timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, ConnectionError, ValueError) as exc:
        raise RuntimeError(
            f"Ollama server is not reachable at {base_url}. Start it with 'ollama serve'."
        ) from exc

    models = payload.get("models", [])
    available_names = {model.get("name", "") for model in models if isinstance(model, dict)}
    requested_name = settings.ollama_model

    if requested_name in available_names:
        return requested_name

    fallback_candidates = [requested_name, "qwen2.5:3b", "qwen2.5:latest", "qwen2.5:7b", "llama3.2"]
    for candidate in fallback_candidates:
        if candidate in available_names:
            return candidate

    raise RuntimeError(
        f"Ollama model '{requested_name}' is not available. Pull it with 'ollama pull {requested_name}'."
    )


def build_llm(settings: Settings) -> BaseChatModel:
    provider = settings.llm_provider.lower().strip()

    if provider == "ollama":
        resolved_model = _check_ollama_availability(settings)
        return ChatOllama(
            model=resolved_model,
            base_url=settings.ollama_base_url,
            temperature=0,
            num_predict=128,
            num_ctx=4096,
            keep_alive="5m",
        )

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini.")
        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0,
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")

