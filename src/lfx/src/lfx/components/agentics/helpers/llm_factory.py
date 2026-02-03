"""Factory functions for creating LLM instances."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.base.models.watsonx_constants import IBM_WATSONX_URLS
from lfx.components.agentics.constants import (
    DEFAULT_OLLAMA_URL,
    ERROR_UNSUPPORTED_PROVIDER,
    LLM_MODEL_PREFIXES,
    PROVIDER_ANTHROPIC,
    PROVIDER_GOOGLE,
    PROVIDER_IBM_WATSONX,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    WATSONX_DEFAULT_MAX_INPUT_TOKENS,
    WATSONX_DEFAULT_MAX_TOKENS,
    WATSONX_DEFAULT_TEMPERATURE,
)

if TYPE_CHECKING:
    from crewai import LLM


def create_llm(
    provider: str,
    model_name: str,
    api_key: str | None,
    *,
    base_url_ibm_watsonx: str | None = None,
    project_id: str | None = None,
    ollama_base_url: str | None = None,
) -> "LLM":
    """Create LLM instance based on provider.

    Args:
        provider: The LLM provider name.
        model_name: The model name/identifier.
        api_key: The API key for the provider.
        base_url_ibm_watsonx: Base URL for IBM WatsonX (optional).
        project_id: Project ID for IBM WatsonX (optional).
        ollama_base_url: Base URL for Ollama (optional).

    Returns:
        Configured LLM instance.

    Raises:
        ValueError: If the provider is not supported.
    """
    from crewai import LLM

    if provider == PROVIDER_IBM_WATSONX:
        return _create_watsonx_llm(
            model_name=model_name,
            api_key=api_key,
            base_url=base_url_ibm_watsonx or IBM_WATSONX_URLS[0],
            project_id=project_id,
        )

    if provider == PROVIDER_GOOGLE:
        return LLM(model=LLM_MODEL_PREFIXES[PROVIDER_GOOGLE] + model_name, api_key=api_key)

    if provider == PROVIDER_OPENAI:
        return LLM(model=LLM_MODEL_PREFIXES[PROVIDER_OPENAI] + model_name, api_key=api_key)

    if provider == PROVIDER_ANTHROPIC:
        return LLM(model=LLM_MODEL_PREFIXES[PROVIDER_ANTHROPIC] + model_name, api_key=api_key)

    if provider == PROVIDER_OLLAMA:
        return _create_ollama_llm(model_name=model_name, base_url=ollama_base_url)

    raise ValueError(ERROR_UNSUPPORTED_PROVIDER.format(provider=provider))


def _create_watsonx_llm(
    model_name: str,
    api_key: str | None,
    base_url: str,
    project_id: str | None,
) -> "LLM":
    """Create IBM WatsonX LLM instance."""
    from crewai import LLM

    return LLM(
        model=LLM_MODEL_PREFIXES[PROVIDER_IBM_WATSONX] + model_name,
        base_url=base_url,
        project_id=project_id,
        api_key=api_key,
        temperature=WATSONX_DEFAULT_TEMPERATURE,
        max_tokens=WATSONX_DEFAULT_MAX_TOKENS,
        max_input_tokens=WATSONX_DEFAULT_MAX_INPUT_TOKENS,
    )


def _create_ollama_llm(model_name: str, base_url: str | None) -> "LLM":
    """Create Ollama LLM instance."""
    from crewai import LLM

    return LLM(
        model=LLM_MODEL_PREFIXES[PROVIDER_OLLAMA] + model_name,
        base_url=base_url or DEFAULT_OLLAMA_URL,
    )
