"""Model configuration and validation helpers for Agentics components."""

from __future__ import annotations

import warnings
from typing import Any

from lfx.components.agentics.constants import (
    ERROR_MODEL_NOT_SELECTED,
    PROVIDER_IBM_WATSONX,
    PROVIDER_OLLAMA,
)


def validate_model_selection(model: Any) -> tuple[str, str]:
    """Validate and extract model name and provider from component input.

    Ensures the model selection is properly formatted and contains required fields.

    Args:
        model: The model selection from the component input (expected as a list with model dict).

    Returns:
        Tuple of (model_name, provider) extracted from the selection.

    Raises:
        ValueError: If no model is selected, model data is invalid, or required fields are missing.
    """
    if not model or not isinstance(model, list) or len(model) == 0:
        raise ValueError(ERROR_MODEL_NOT_SELECTED)

    model_selection = model[0]

    model_name = model_selection.get("name")
    provider = model_selection.get("provider")

    if not model_name or not provider:
        raise ValueError(ERROR_MODEL_NOT_SELECTED)

    return model_name, provider


# ---------------------------------------------------------------------------
# Deprecated - kept for backward compatibility only
# These functions were superseded by handle_model_input_update() in
# lfx.base.models.unified_models, which centralises provider-field show/hide
# logic across all components.  They will be removed in a future release.
# ---------------------------------------------------------------------------


def update_provider_fields_visibility(
    build_config: dict,
    field_value: Any,
    field_name: str | None,
) -> dict:
    """Deprecated. Use handle_model_input_update() from lfx.base.models.unified_models instead.

    Update visibility of provider-specific fields based on the selected model.

    .. deprecated::
        This function was replaced by the unified ``handle_model_input_update()``
        helper, which additionally refreshes model options and pre-populates
        credential fields from the variable service.  Custom components should
        call ``handle_model_input_update(self, build_config, field_value, field_name)``
        from their ``update_build_config`` method instead.
    """
    warnings.warn(
        "update_provider_fields_visibility is deprecated and will be removed in a future release. "
        "Use handle_model_input_update() from lfx.base.models.unified_models instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    current_model_value = field_value if field_name == "model" else build_config.get("model", {}).get("value")

    if not isinstance(current_model_value, list) or len(current_model_value) == 0:
        return build_config

    selected_model = current_model_value[0]
    provider = selected_model.get("provider", "")

    _update_watsonx_fields(build_config, provider)
    _update_ollama_fields(build_config, provider)

    return build_config


def _update_watsonx_fields(build_config: dict, provider: str) -> None:
    """Deprecated internal helper - absorbed into handle_model_input_update()."""
    is_watsonx = provider == PROVIDER_IBM_WATSONX

    if "base_url_ibm_watsonx" in build_config:
        build_config["base_url_ibm_watsonx"]["show"] = is_watsonx
        build_config["base_url_ibm_watsonx"]["required"] = is_watsonx

    if "project_id" in build_config:
        build_config["project_id"]["show"] = is_watsonx
        build_config["project_id"]["required"] = is_watsonx


def _update_ollama_fields(build_config: dict, provider: str) -> None:
    """Deprecated internal helper - absorbed into handle_model_input_update()."""
    is_ollama = provider == PROVIDER_OLLAMA

    if "ollama_base_url" in build_config:
        build_config["ollama_base_url"]["show"] = is_ollama
