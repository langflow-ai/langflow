"""Gemini Live speech-to-speech service component.

Single-model voice agent — STT + LLM + TTS are all handled inside Pipecat's
``GeminiLiveLLMService``. Use this instead of separate STT/LLM/TTS components
when you want native-audio Gemini Live.
"""

from lfx.base.pipecat.service import PipecatServiceComponent
from lfx.field_typing.voice_types import PipecatS2SService
from lfx.io import DropdownInput, HandleInput, MultilineInput, Output, SecretStrInput


# Available Gemini Live model IDs (kept in one place so the dropdown stays current).
GEMINI_LIVE_MODELS = [
    "models/gemini-2.5-flash-native-audio-preview-12-2025",
    "models/gemini-2.5-flash-preview-native-audio-dialog",
    "models/gemini-2.0-flash-live-001",
    "models/gemini-2.0-flash-exp",
]

# Voice options for Gemini Live (subset; full list documented at Google's site).
GEMINI_LIVE_VOICES = ["Aoede", "Charon", "Fenrir", "Kore", "Puck", "Zephyr"]


class GeminiLiveLLMServiceComponent(PipecatServiceComponent):
    display_name = "Gemini Live (S2S)"
    description = "Google Gemini Live — real-time native-audio speech-to-speech LLM."
    icon = "Sparkles"
    name = "GeminiLiveLLM"

    inputs = [
        SecretStrInput(name="api_key", display_name="Google API Key", required=True),
        DropdownInput(
            name="model",
            display_name="Model",
            options=GEMINI_LIVE_MODELS,
            value=GEMINI_LIVE_MODELS[0],
        ),
        DropdownInput(
            name="voice_id",
            display_name="Voice",
            options=GEMINI_LIVE_VOICES,
            value="Kore",
        ),
        MultilineInput(
            name="system_instruction",
            display_name="System Instruction",
            value="",
            info="System prompt sent to Gemini Live at session start.",
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["PipecatTool"],
            is_list=True,
            required=False,
        ),
    ]

    outputs = [
        Output(
            display_name="S2S LLM",
            name="llm",
            method="build_service",
            types=["PipecatS2SService", "PipecatLLMService", "PipecatFrameProcessor"],
        ),
    ]

    def build_service(self) -> PipecatS2SService:
        from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService

        service = GeminiLiveLLMService(
            api_key=self.api_key,
            model=self.model,
            voice_id=self.voice_id or "Kore",
            system_instruction=self.system_instruction or None,
        )
        self._register_tools(service)
        return service
