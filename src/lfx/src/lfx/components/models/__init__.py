"""Models module - backwards compatibility alias for models_and_agents.

This module provides backwards compatibility by forwarding model-related imports
to models_and_agents where the actual model components are located.
"""

from __future__ import annotations

import sys
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

# Register redirected submodules in sys.modules for direct importlib.import_module() calls
# This allows imports like: import lfx.components.models.embedding_model
_redirected_submodules = {
    "lfx.components.models.embedding_model": "lfx.components.models_and_agents.embedding_model",
    "lfx.components.models.language_model": "lfx.components.models_and_agents.language_model",
}

for old_path, new_path in _redirected_submodules.items():
    if old_path not in sys.modules:
        # Use a lazy loader that imports the actual module when accessed
        class _RedirectedModule:
            def __init__(self, target_path: str, original_path: str):
                self._target_path = target_path
                self._original_path = original_path
                self._module = None

            def __getattr__(self, name: str) -> Any:
                if self._module is None:
                    from importlib import import_module

                    self._module = import_module(self._target_path)
                    # Also register under the original path for future imports
                    sys.modules[self._original_path] = self._module
                return getattr(self._module, name)

            def __repr__(self) -> str:
                return f"<redirected module '{self._original_path}' -> '{self._target_path}'>"

        sys.modules[old_path] = _RedirectedModule(new_path, old_path)


def __getattr__(attr_name: str) -> Any:
    """Forward attribute access to models_and_agents components."""
    # Handle submodule access for backwards compatibility
    if attr_name == "embedding_model":
        from importlib import import_module

        result = import_module("lfx.components.models_and_agents.embedding_model")
        globals()[attr_name] = result
        return result
    if attr_name == "language_model":
        from importlib import import_module

        result = import_module("lfx.components.models_and_agents.language_model")
        globals()[attr_name] = result
        return result

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
