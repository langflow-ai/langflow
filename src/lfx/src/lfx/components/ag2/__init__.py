from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .ag2_agent import AG2AgentComponent
    from .ag2_groupchat import AG2GroupChatComponent
    from .ag2_llm_config import AG2LLMConfigComponent
    from .ag2_tool_agent import AG2ToolAgentComponent

_dynamic_imports = {
    "AG2AgentComponent": "ag2_agent",
    "AG2GroupChatComponent": "ag2_groupchat",
    "AG2LLMConfigComponent": "ag2_llm_config",
    "AG2ToolAgentComponent": "ag2_tool_agent",
}

__all__ = [
    "AG2AgentComponent",
    "AG2GroupChatComponent",
    "AG2LLMConfigComponent",
    "AG2ToolAgentComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import ag2 components on attribute access."""
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
