"""OpenAI / Whisper speech-to-text service component."""

from lfx.base.pipecat.service import PipecatServiceComponent
from lfx.field_typing.voice_types import PipecatSTTService
from lfx.io import DropdownInput, Output, SecretStrInput


class OpenAISTTServiceComponent(PipecatServiceComponent):
    display_name = "OpenAI STT"
    description = "Speech-to-text via OpenAI's Whisper / gpt-4o-transcribe APIs."
    icon = "Mic"
    name = "OpenAISTT"

    inputs = [
        SecretStrInput(name="api_key", display_name="OpenAI API Key", required=True),
        DropdownInput(
            name="model",
            display_name="Model",
            options=["whisper-1", "gpt-4o-transcribe", "gpt-4o-mini-transcribe"],
            value="gpt-4o-mini-transcribe",
        ),
    ]

    outputs = [
        Output(
            display_name="STT",
            name="stt",
            method="build_service",
            types=["PipecatSTTService", "PipecatFrameProcessor"],
        ),
    ]

    def build_service(self) -> PipecatSTTService:
        from pipecat.services.openai.stt import OpenAISTTService

        return OpenAISTTService(api_key=self.api_key, model=self.model)
