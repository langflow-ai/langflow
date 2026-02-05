"""LLM setup utilities for Agentics components."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.base.models.unified_models import get_api_key_for_provider
from lfx.components.agentics.constants import (
    ERROR_API_KEY_REQUIRED,
    PROVIDER_OLLAMA,
)
from lfx.components.agentics.helpers.llm_factory import create_llm
from lfx.components.agentics.helpers.model_config import validate_model_selection

if TYPE_CHECKING:
    from crewai import LLM

    from lfx.custom.custom_component.component import Component


def prepare_llm_from_component(component: Component) -> LLM:
    """Prepare and configure LLM from component settings.

    Args:
        component: The Agentics component instance.

    Returns:
        Configured LLM instance.

    Raises:
        ValueError: If model is not selected or API key is missing.
    """
    model_name, provider = validate_model_selection(component.model)
    api_key = get_api_key_for_provider(component.user_id, provider, component.api_key)

    if not api_key and provider != PROVIDER_OLLAMA:
        raise ValueError(ERROR_API_KEY_REQUIRED.format(provider=provider))

    return create_llm(
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        base_url_ibm_watsonx=getattr(component, "base_url_ibm_watsonx", None),
        project_id=getattr(component, "project_id", None),
        ollama_base_url=getattr(component, "ollama_base_url", None),
    )
