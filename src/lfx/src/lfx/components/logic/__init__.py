"""Logic module - backwards compatibility alias for flow_controls.

This module provides backwards compatibility by forwarding imports
to flow_controls where the actual logic components are located.
"""

from __future__ import annotations

import sys
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

# Register redirected submodules in sys.modules for direct importlib.import_module() calls
# This allows imports like: import lfx.components.logic.listen
_redirected_submodules = {
    "lfx.components.logic.listen": "lfx.components.flow_controls.listen",
    "lfx.components.logic.loop": "lfx.components.flow_controls.loop",
    "lfx.components.logic.notify": "lfx.components.flow_controls.notify",
    "lfx.components.logic.pass_message": "lfx.components.flow_controls.pass_message",
    "lfx.components.logic.conditional_router": "lfx.components.flow_controls.conditional_router",
    "lfx.components.logic.data_conditional_router": "lfx.components.flow_controls.data_conditional_router",
    "lfx.components.logic.flow_tool": "lfx.components.flow_controls.flow_tool",
    "lfx.components.logic.run_flow": "lfx.components.flow_controls.run_flow",
    "lfx.components.logic.sub_flow": "lfx.components.flow_controls.sub_flow",
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
    """Lazily import logic components on attribute access."""
    # Handle submodule access for backwards compatibility
    if attr_name == "listen":
        from importlib import import_module

        result = import_module("lfx.components.flow_controls.listen")
        globals()[attr_name] = result
        return result
    if attr_name == "loop":
        from importlib import import_module

        result = import_module("lfx.components.flow_controls.loop")
        globals()[attr_name] = result
        return result
    if attr_name == "notify":
        from importlib import import_module

        result = import_module("lfx.components.flow_controls.notify")
        globals()[attr_name] = result
        return result
    if attr_name == "pass_message":
        from importlib import import_module

        result = import_module("lfx.components.flow_controls.pass_message")
        globals()[attr_name] = result
        return result
    if attr_name == "conditional_router":
        from importlib import import_module

        result = import_module("lfx.components.flow_controls.conditional_router")
        globals()[attr_name] = result
        return result
    if attr_name == "data_conditional_router":
        from importlib import import_module

        result = import_module("lfx.components.flow_controls.data_conditional_router")
        globals()[attr_name] = result
        return result
    if attr_name == "flow_tool":
        from importlib import import_module

        result = import_module("lfx.components.flow_controls.flow_tool")
        globals()[attr_name] = result
        return result
    if attr_name == "run_flow":
        from importlib import import_module

        result = import_module("lfx.components.flow_controls.run_flow")
        globals()[attr_name] = result
        return result
    if attr_name == "sub_flow":
        from importlib import import_module

        result = import_module("lfx.components.flow_controls.sub_flow")
        globals()[attr_name] = result
        return result

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
