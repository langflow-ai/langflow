"""Models module - backwards compatibility alias for models_and_agents.

This module provides backwards compatibility by forwarding model-related imports
to models_and_agents where the actual model components are located.
"""

from __future__ import annotations

from typing import Any

from lfx.components._importing import import_mod

# Forward model components from models_and_agents
_dynamic_imports = {
    "LanguageModelComponent": "language_model",
    "EmbeddingModelComponent": "embedding_model",
}

__all__ = [
    "EmbeddingModelComponent",
    "LanguageModelComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Forward attribute access to models_and_agents components."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)

    # Import from models_and_agents using the correct package path
    package = "lfx.components.models_and_agents"
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], package)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    """Return directory of available components."""
    return list(__all__)
