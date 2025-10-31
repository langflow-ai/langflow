from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from lfx.components.llm_operations.batch_run import BatchRunComponent
    from lfx.components.llm_operations.lambda_filter import SmartTransformComponent
    from lfx.components.llm_operations.llm_conditional_router import SmartRouterComponent
    from lfx.components.llm_operations.llm_router import LLMRouterComponent
    from lfx.components.llm_operations.structured_output import StructuredOutputComponent

_dynamic_imports = {
    "BatchRunComponent": "batch_run",
    "SmartTransformComponent": "lambda_filter",
    "SmartRouterComponent": "llm_conditional_router",
    "LLMRouterComponent": "llm_router",
    "StructuredOutputComponent": "structured_output",
}

__all__ = [
    "BatchRunComponent",
    "LLMRouterComponent",
    "SmartRouterComponent",
    "SmartTransformComponent",
    "StructuredOutputComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import LLM operation components on attribute access."""
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
