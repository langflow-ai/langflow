"""Langflow knowledge bases module - forwards to lfx.components.files_and_knowledge.

This module provides backwards compatibility by forwarding all imports
to files_and_knowledge where the actual knowledge base components are located.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import types

from lfx.components.files_and_knowledge import __all__ as _lfx_all

__all__: list[str] = list(_lfx_all)

# Register redirected submodules in sys.modules for direct importlib.import_module() calls
# This allows imports like: import langflow.components.knowledge_bases.ingestion
_redirected_submodules = {
    "langflow.components.knowledge_bases.ingestion": "lfx.components.files_and_knowledge.ingestion",
    "langflow.components.knowledge_bases.retrieval": "lfx.components.files_and_knowledge.retrieval",
}

for old_path, new_path in _redirected_submodules.items():
    if old_path not in sys.modules:
        # Use a lazy loader that imports the actual module when accessed
        class _RedirectedModule:
            _module: types.ModuleType | None

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

        sys.modules[old_path] = _RedirectedModule(new_path, old_path)  # type: ignore[assignment]


def __getattr__(attr_name: str) -> Any:
    """Forward attribute access to lfx.components.files_and_knowledge."""
    # Handle submodule access for backwards compatibility
    if attr_name == "ingestion":
        from importlib import import_module

        result = import_module("lfx.components.files_and_knowledge.ingestion")
        globals()[attr_name] = result
        return result
    if attr_name == "retrieval":
        from importlib import import_module

        result = import_module("lfx.components.files_and_knowledge.retrieval")
        globals()[attr_name] = result
        return result

    from lfx.components import files_and_knowledge

    return getattr(files_and_knowledge, attr_name)


def __dir__() -> list[str]:
    """Forward dir() to lfx.components.files_and_knowledge."""
    return list(__all__)
