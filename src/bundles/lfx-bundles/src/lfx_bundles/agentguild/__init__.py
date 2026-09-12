"""Agent Guild endpoint inspection and pricing components."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.utils.lazy_import import import_mod

if TYPE_CHECKING:
    from .agentguild_paid_operations import AgentGuildPaidOperations
    from .agentguild_preflight import AgentGuildPreflight

_dynamic_imports = {
    "AgentGuildPaidOperations": "agentguild_paid_operations",
    "AgentGuildPreflight": "agentguild_preflight",
}

__all__ = ["AgentGuildPaidOperations", "AgentGuildPreflight"]


def __getattr__(attr_name: str) -> Any:
    """Lazily import the requested component."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
