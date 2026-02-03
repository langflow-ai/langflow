"""Model configuration helpers for Agentics components."""

from __future__ import annotations

from typing import Any

from lfx.components.agentics.constants import (
    ERROR_MODEL_NOT_SELECTED,
    PROVIDER_IBM_WATSONX,
    PROVIDER_OLLAMA,
)


def validate_model_selection(model: Any) -> tuple[str, str]:
    """Validate and extract model selection.

    Args:
        model: The model selection from the component input.

    Returns:
        Tuple of (model_name, provider).

    Raises:
        ValueError: If no model is selected or model data is invalid.
    """
    if not model or not isinstance(model, list) or len(model) == 0:
        raise ValueError(ERROR_MODEL_NOT_SELECTED)

    model_selection = model[0]

    model_name = model_selection.get("name")
    provider = model_selection.get("provider")

    if not model_name or not provider:
        raise ValueError(ERROR_MODEL_NOT_SELECTED)

    return model_name, provider


def update_provider_fields_visibility(
    build_config: dict,
    field_value: Any,
    field_name: str | None,
) -> dict:
    """Update visibility of provider-specific fields based on selected model.

    Args:
        build_config: The build configuration dictionary.
        field_value: The current field value.
        field_name: The name of the field being updated.

    Returns:
        Updated build configuration.
    """
    current_model_value = field_value if field_name == "model" else build_config.get("model", {}).get("value")

    if not isinstance(current_model_value, list) or len(current_model_value) == 0:
        return build_config

    selected_model = current_model_value[0]
    provider = selected_model.get("provider", "")

    _update_watsonx_fields(build_config, provider)
    _update_ollama_fields(build_config, provider)

    return build_config


def _update_watsonx_fields(build_config: dict, provider: str) -> None:
    """Update WatsonX-specific field visibility."""
    is_watsonx = provider == PROVIDER_IBM_WATSONX

    if "base_url_ibm_watsonx" in build_config:
        build_config["base_url_ibm_watsonx"]["show"] = is_watsonx
        build_config["base_url_ibm_watsonx"]["required"] = is_watsonx

    if "project_id" in build_config:
        build_config["project_id"]["show"] = is_watsonx
        build_config["project_id"]["required"] = is_watsonx


def _update_ollama_fields(build_config: dict, provider: str) -> None:
    """Update Ollama-specific field visibility."""
    is_ollama = provider == PROVIDER_OLLAMA

    if "ollama_base_url" in build_config:
        build_config["ollama_base_url"]["show"] = is_ollama
