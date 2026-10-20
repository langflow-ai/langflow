from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from lfx.components.llm_operations.batch_run import BatchRunComponent
    from lfx.components.llm_operations.guardrails_v2 import GuardrailsV2Component
    from lfx.components.llm_operations.lambda_filter import SmartTransformComponent
    from lfx.components.llm_operations.llm_conditional_router import SmartRouterComponent
    from lfx.components.llm_operations.llm_selector import LLMSelectorComponent
    from lfx.components.llm_operations.openai_decision import OpenAIDecisionComponent
    from lfx.components.llm_operations.perplexity_decision import PerplexityDecisionComponent
    from lfx.components.llm_operations.structured_output import StructuredOutputComponent
    from lfx.components.llm_operations.typesafe_decision import TypeSafeDecisionComponent

_dynamic_imports = {
    "BatchRunComponent": "batch_run",
    "GuardrailsV2Component": "guardrails_v2",
    "SmartTransformComponent": "lambda_filter",
    "SmartRouterComponent": "llm_conditional_router",
    "LLMSelectorComponent": "llm_selector",
    "OpenAIDecisionComponent": "openai_decision",
    "PerplexityDecisionComponent": "perplexity_decision",
    "StructuredOutputComponent": "structured_output",
    "TypeSafeDecisionComponent": "typesafe_decision",
}

__all__ = [
    "BatchRunComponent",
    "GuardrailsV2Component",
    "LLMSelectorComponent",
    "OpenAIDecisionComponent",
    "PerplexityDecisionComponent",
    "SmartRouterComponent",
    "SmartTransformComponent",
    "StructuredOutputComponent",
    "TypeSafeDecisionComponent",
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
