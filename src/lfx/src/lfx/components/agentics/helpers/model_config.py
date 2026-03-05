"""Model configuration and validation helpers for Agentics components."""

from __future__ import annotations

from typing import Any

from lfx.components.agentics.constants import ERROR_MODEL_NOT_SELECTED


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
