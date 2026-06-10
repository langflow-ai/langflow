"""`call_llm` — the single entry point every Lothal phase engine calls (Story 0.1).

Provider-agnostic: it validates the shared message shape, resolves the
configured provider, and returns the assistant reply as a string. Swapping or
adding a model never touches this function.
"""

from __future__ import annotations

from typing import Any

import langflow.lothal.llm.providers  # noqa: F401  -- import registers built-in providers
from langflow.lothal.llm.base import Message, validate_messages
from langflow.lothal.llm.registry import get_provider


async def call_llm(
    messages: list[Message],
    *,
    provider: str | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> str:
    """Send `messages` to the configured LLM and return the reply text.

    `messages` is the OpenAI-style list of `{"role", "content"}` dicts.
    `provider` overrides `$LOTHAL_LLM_PROVIDER` and `model` overrides the
    provider's env default (`$LOTHAL_MODEL_NAME`) for this call — both are meant
    to be set by higher-level callers (e.g. per phase engine). Extra `kwargs`
    pass through to the provider.

    Raises `LLMConfigError` on bad config/input and `LLMConnectionError` on a
    failed or empty model call.
    """
    validate_messages(messages)
    if model is not None:
        kwargs["model"] = model
    return await get_provider(provider).complete(messages, **kwargs)
