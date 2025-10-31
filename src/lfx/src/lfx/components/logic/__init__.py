from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from lfx.components.logic.conditional_router import ConditionalRouterComponent
    from lfx.components.logic.data_conditional_router import DataConditionalRouterComponent
    from lfx.components.logic.flow_tool import FlowToolComponent
    from lfx.components.logic.llm_conditional_router import SmartRouterComponent
    from lfx.components.logic.loop import LoopComponent
    from lfx.components.logic.pass_message import PassMessageComponent
    from lfx.components.logic.run_flow import RunFlowComponent
    from lfx.components.logic.sub_flow import SubFlowComponent

_dynamic_imports = {
    "ConditionalRouterComponent": "conditional_router",
    "DataConditionalRouterComponent": "data_conditional_router",
    "FlowToolComponent": "flow_tool",
    "LoopComponent": "loop",
    "PassMessageComponent": "pass_message",
    "RunFlowComponent": "run_flow",
    "SmartRouterComponent": "llm_conditional_router",
    "SubFlowComponent": "sub_flow",
}

__all__ = [
    "ConditionalRouterComponent",
    "DataConditionalRouterComponent",
    "FlowToolComponent",
    "LoopComponent",
    "PassMessageComponent",
    "RunFlowComponent",
    "SmartRouterComponent",
    "SubFlowComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import logic components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)

    # Most logic components were moved to flow_controls
    # Forward them to flow_controls for backwards compatibility
    if attr_name in (
        "ConditionalRouterComponent",
        "DataConditionalRouterComponent",
        "FlowToolComponent",
        "LoopComponent",
        "PassMessageComponent",
        "RunFlowComponent",
        "SubFlowComponent",
    ):
        from lfx.components import flow_controls

        result = getattr(flow_controls, attr_name)
        globals()[attr_name] = result
        return result

    # SmartRouterComponent was moved to llm_operations
    if attr_name == "SmartRouterComponent":
        from lfx.components import llm_operations

        result = getattr(llm_operations, attr_name)
        globals()[attr_name] = result
        return result

    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
