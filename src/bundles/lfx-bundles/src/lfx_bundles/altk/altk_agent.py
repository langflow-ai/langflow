"""Legacy bundle import for the provider-free ALTK retirement component."""

from lfx.components.altk.altk_agent import (
    INPUT_NAMES_TO_BE_OVERRIDDEN,
    MODEL_PROVIDERS_LIST,
    VERBOSE_INPUT_INFO,
    ALTKAgentComponent,
    get_parent_agent_inputs,
    set_advanced_true,
)

__all__ = [
    "INPUT_NAMES_TO_BE_OVERRIDDEN",
    "MODEL_PROVIDERS_LIST",
    "VERBOSE_INPUT_INFO",
    "ALTKAgentComponent",
    "get_parent_agent_inputs",
    "set_advanced_true",
]
