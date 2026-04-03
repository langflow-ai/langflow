"""Shared validation helpers for Watsonx resource_name_prefix handling."""

from __future__ import annotations

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    WXO_RESOURCE_NAME_PREFIX_MAX_LENGTH,
    WXO_RESOURCE_NAME_PREFIX_NAMESPACE,
    WXO_SANITIZE_RE,
    WXO_TRANSLATE,
)


def validate_resource_name_prefix_for_provider(caller_prefix: str) -> str:
    """Validate and normalize a caller prefix to the provider-facing ``lf_`` namespace."""
    if not isinstance(caller_prefix, str) or not caller_prefix.strip():
        msg = "resource_name_prefix must be a non-empty string."
        raise ValueError(msg)

    # Fail fast on raw caller-provided length before sanitize/normalize transforms
    # so callers can quickly debug oversized input values.
    caller_prefix_trimmed = caller_prefix.strip()
    if len(caller_prefix_trimmed) > WXO_RESOURCE_NAME_PREFIX_MAX_LENGTH:
        msg = f"resource_name_prefix cannot exceed {WXO_RESOURCE_NAME_PREFIX_MAX_LENGTH} characters."
        raise ValueError(msg)

    validated = WXO_SANITIZE_RE.sub("", caller_prefix.translate(WXO_TRANSLATE))
    if not validated:
        msg = "resource_name_prefix must contain at least one alphanumeric character."
        raise ValueError(msg)
    if not validated[0].isalpha():
        msg = "resource_name_prefix must start with a letter."
        raise ValueError(msg)

    normalized_prefix = (
        validated
        if validated.startswith(WXO_RESOURCE_NAME_PREFIX_NAMESPACE)
        else f"{WXO_RESOURCE_NAME_PREFIX_NAMESPACE}{validated}"
    )
    if len(normalized_prefix) > WXO_RESOURCE_NAME_PREFIX_MAX_LENGTH:
        if validated.startswith(WXO_RESOURCE_NAME_PREFIX_NAMESPACE):
            msg = f"resource_name_prefix cannot exceed {WXO_RESOURCE_NAME_PREFIX_MAX_LENGTH} characters."
        else:
            max_without_prefix = WXO_RESOURCE_NAME_PREFIX_MAX_LENGTH - len(WXO_RESOURCE_NAME_PREFIX_NAMESPACE)
            msg = (
                f"resource_name_prefix cannot exceed {WXO_RESOURCE_NAME_PREFIX_MAX_LENGTH} characters after "
                f"normalization. Inputs without the '{WXO_RESOURCE_NAME_PREFIX_NAMESPACE}' namespace are normalized "
                "by adding it, so the maximum "
                f"length without '{WXO_RESOURCE_NAME_PREFIX_NAMESPACE}' is {max_without_prefix}."
            )
        raise ValueError(msg)

    return normalized_prefix
