"""Provider registry — the open/closed seam for adding models/services.

A provider becomes selectable simply by being defined with `@register_provider`;
`get_provider` looks it up by name (explicit arg → `$LOTHAL_LLM_PROVIDER` →
`claude`). Nothing above this layer changes when a provider is added.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from langflow.lothal.llm.errors import LLMConfigError

if TYPE_CHECKING:
    from langflow.lothal.llm.base import LLMProvider

DEFAULT_PROVIDER = "claude"

_REGISTRY: dict[str, type[LLMProvider]] = {}


def register_provider(cls: type[LLMProvider]) -> type[LLMProvider]:
    """Class decorator: register `cls` under its normalized `name`.

    Names are normalized (stripped + lowercased) so registration and
    `get_provider` lookup always agree; a duplicate name is rejected rather than
    silently overwriting an existing provider.
    """
    raw_name = getattr(cls, "name", None)
    if not isinstance(raw_name, str) or not raw_name.strip():
        msg = f"{cls.__name__} must define a non-empty string `name` to be registered."
        raise LLMConfigError(msg)
    name = raw_name.strip().lower()
    if name in _REGISTRY:
        msg = f"LLM provider name {name!r} is already registered to {_REGISTRY[name].__name__}."
        raise LLMConfigError(msg)
    _REGISTRY[name] = cls
    return cls


def available_providers() -> list[str]:
    """Sorted names of every registered provider."""
    return sorted(_REGISTRY)


def get_provider(name: str | None = None) -> LLMProvider:
    """Resolve and construct a provider by name.

    Precedence: explicit `name` arg → `$LOTHAL_LLM_PROVIDER` → `DEFAULT_PROVIDER`.
    An unknown name raises `LLMConfigError` listing what is available.
    """
    resolved = (name or os.getenv("LOTHAL_LLM_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    try:
        cls = _REGISTRY[resolved]
    except KeyError as exc:
        msg = f"Unknown LLM provider {resolved!r}; available: {available_providers()}."
        raise LLMConfigError(msg) from exc
    return cls.from_env()
