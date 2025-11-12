from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from lfx.components.models_and_agents.agent import AgentComponent
    from lfx.components.models_and_agents.altk_agent import ALTKAgentComponent
    from lfx.components.models_and_agents.cuga_agent import CugaComponent
    from lfx.components.models_and_agents.embedding_model import EmbeddingModelComponent
    from lfx.components.models_and_agents.language_model import LanguageModelComponent
    from lfx.components.models_and_agents.mcp_component import MCPToolsComponent
    from lfx.components.models_and_agents.memory import MemoryComponent
    from lfx.components.models_and_agents.prompt import PromptComponent

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
    """Lazily import model and agent components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
