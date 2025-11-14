"""Agents module - backwards compatibility alias for models_and_agents.

This module provides backwards compatibility by forwarding all imports
to models_and_agents where the actual agent components are located.
"""

from __future__ import annotations

from typing import Any

from lfx.components._importing import import_mod

# Replicate the same dynamic imports as models_and_agents
_dynamic_imports = {
    "AgentComponent": "agent",
    "ALTKAgentComponent": "altk_agent",
    "CugaComponent": "cuga_agent",
    "EmbeddingModelComponent": "embedding_model",
    "LanguageModelComponent": "language_model",
    "MCPToolsComponent": "mcp_component",
    "MemoryComponent": "memory",
    "PromptComponent": "prompt",
}

__all__ = [
    "ALTKAgentComponent",
    "AgentComponent",
    "CugaComponent",
    "EmbeddingModelComponent",
    "LanguageModelComponent",
    "MCPToolsComponent",
    "MemoryComponent",
    "PromptComponent",
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
