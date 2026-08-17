# llm_client.py - thin wrapper around Ollama's OpenAI-compatible endpoint.
#
# Pattern adapted from vaidz-llm/backend/agent_core.py:210-226 (the
# `_get_client` local-tier branch): a single `openai.OpenAI` client pointed
# at Ollama, since Ollama exposes both local and "-cloud" hosted models
# through the same http://localhost:11434/v1 API.

from typing import Any, Optional

from openai import OpenAI

from . import config

_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=config.OLLAMA_BASE_URL,
            api_key=config.OLLAMA_API_KEY,
            max_retries=0,
        )
    return _client


def complete(
    model: str,
    messages: list[dict],
    tools: Optional[list[dict]] = None,
    tool_choice: Optional[str] = None,
    **kwargs: Any,
):
    """Single chat-completion call. Returns the raw OpenAI ChatCompletion object.

    Raises the underlying openai.APIStatusError (e.g. HTTP 400) unmodified if
    `model` doesn't support tool calls - callers are expected to have already
    picked a model known to support tools (see config.py's landmine note)
    rather than silently falling back here.
    """
    client = get_client()
    request_kwargs: dict[str, Any] = {"model": model, "messages": messages}
    if tools:
        request_kwargs["tools"] = tools
        request_kwargs["tool_choice"] = tool_choice or "auto"
    request_kwargs.update(kwargs)
    return client.chat.completions.create(**request_kwargs)
