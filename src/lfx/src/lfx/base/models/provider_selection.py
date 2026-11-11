"""Read raw provider selectors without hydrating inputs or constructing models."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

CANONICAL_MODEL_INPUT = "model"
MODEL_PROVIDER_OVERRIDE_INPUT = "provider"
LEGACY_MODEL_PROVIDER_INPUT = "agent_llm"
CUSTOM_MODEL_PROVIDER = "Custom"


def raw_model_provider_names(model_input_names: Iterable[str], parameters: Mapping[str, Any]) -> tuple[str, ...]:
    """Keep the runtime's first-selection and canonical override semantics."""
    providers: list[str] = []
    for name in model_input_names:
        selection = parameters.get(name)
        if isinstance(selection, Mapping):
            selection = [selection]
        if not isinstance(selection, list) or not selection or not isinstance(selection[0], Mapping):
            continue
        override = parameters.get(MODEL_PROVIDER_OVERRIDE_INPUT) if name == CANONICAL_MODEL_INPUT else None
        provider = override.strip() if isinstance(override, str) else ""
        if not provider:
            selected = selection[0].get("provider")
            provider = selected.strip() if isinstance(selected, str) else ""
        if provider and provider not in providers:
            providers.append(provider)
    legacy = parameters.get(LEGACY_MODEL_PROVIDER_INPUT)
    if isinstance(legacy, str):
        legacy = legacy.strip()
        if legacy and legacy != CUSTOM_MODEL_PROVIDER and legacy not in providers:
            providers.append(legacy)
    return tuple(providers)
