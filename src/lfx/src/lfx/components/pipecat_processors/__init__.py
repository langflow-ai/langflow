"""Pipecat frame-processor components.

These are the non-service primitives placed between transport.input() and
transport.output(): VAD analyzers, LLM context + aggregator pair, and any
custom FrameProcessor (e.g. MicGate to mute the user input while the bot is
speaking).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from lfx.components.pipecat_processors.llm_context import LLMContextComponent
    from lfx.components.pipecat_processors.llm_context_aggregator_pair import LLMContextAggregatorPairComponent
    from lfx.components.pipecat_processors.mic_gate import MicGateProcessorComponent
    from lfx.components.pipecat_processors.silero_vad import SileroVADComponent

_dynamic_imports = {
    "LLMContextAggregatorPairComponent": "llm_context_aggregator_pair",
    "LLMContextComponent": "llm_context",
    "MicGateProcessorComponent": "mic_gate",
    "SileroVADComponent": "silero_vad",
}

__all__ = [
    "LLMContextAggregatorPairComponent",
    "LLMContextComponent",
    "MicGateProcessorComponent",
    "SileroVADComponent",
]


def __getattr__(attr_name: str) -> Any:
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
