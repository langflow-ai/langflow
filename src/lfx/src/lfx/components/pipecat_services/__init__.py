"""Pipecat service components: STT / LLM / TTS / S2S.

Each provider lives in one file extending ``PipecatServiceComponent``. The
component's ``build_service()`` returns a live Pipecat service object
(``DeepgramSTTService``, ``OpenAILLMService``, ``ElevenLabsTTSService``, etc.)
which the terminal ``VoicePipelineComponent`` slots into the pipeline.

LLM / S2S components inherit ``tools`` input handling from the base class so
any ``VoiceToolComponent`` can be wired in and registered automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from lfx.components.pipecat_services.anthropic_llm import AnthropicLLMServiceComponent
    from lfx.components.pipecat_services.cartesia_tts import CartesiaTTSServiceComponent
    from lfx.components.pipecat_services.deepgram_stt import DeepgramSTTServiceComponent
    from lfx.components.pipecat_services.elevenlabs_tts import ElevenLabsTTSServiceComponent
    from lfx.components.pipecat_services.gemini_live_s2s import GeminiLiveLLMServiceComponent
    from lfx.components.pipecat_services.google_llm import GoogleLLMServiceComponent
    from lfx.components.pipecat_services.openai_llm import OpenAILLMServiceComponent
    from lfx.components.pipecat_services.openai_stt import OpenAISTTServiceComponent
    from lfx.components.pipecat_services.openai_tts import OpenAITTSServiceComponent

_dynamic_imports = {
    "AnthropicLLMServiceComponent": "anthropic_llm",
    "CartesiaTTSServiceComponent": "cartesia_tts",
    "DeepgramSTTServiceComponent": "deepgram_stt",
    "ElevenLabsTTSServiceComponent": "elevenlabs_tts",
    "GeminiLiveLLMServiceComponent": "gemini_live_s2s",
    "GoogleLLMServiceComponent": "google_llm",
    "OpenAILLMServiceComponent": "openai_llm",
    "OpenAISTTServiceComponent": "openai_stt",
    "OpenAITTSServiceComponent": "openai_tts",
}

__all__ = [
    "AnthropicLLMServiceComponent",
    "CartesiaTTSServiceComponent",
    "DeepgramSTTServiceComponent",
    "ElevenLabsTTSServiceComponent",
    "GeminiLiveLLMServiceComponent",
    "GoogleLLMServiceComponent",
    "OpenAILLMServiceComponent",
    "OpenAISTTServiceComponent",
    "OpenAITTSServiceComponent",
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
