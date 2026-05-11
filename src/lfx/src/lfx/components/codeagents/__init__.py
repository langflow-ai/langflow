from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from lfx.components.codeagents.codeact_agent_smolagents import CodeActAgentSmolagentsComponent
    from lfx.components.codeagents.open_ds_star_agent import OpenDsStarAgentComponent

_dynamic_imports = {
    "CodeActAgentSmolagentsComponent": "codeact_agent_smolagents",
    "OpenDsStarAgentComponent": "open_ds_star_agent",
}

__all__ = [
    "CodeActAgentSmolagentsComponent",
    "OpenDsStarAgentComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import code agents components on attribute access."""
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
