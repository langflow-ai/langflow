"""OpenAI text-to-speech service component."""

from lfx.base.pipecat.service import PipecatServiceComponent
from lfx.field_typing.voice_types import PipecatTTSService
from lfx.io import DropdownInput, IntInput, Output, SecretStrInput


class OpenAITTSServiceComponent(PipecatServiceComponent):
    display_name = "OpenAI TTS"
    description = "Text-to-speech via OpenAI's tts-1 / gpt-4o-mini-tts APIs."
    icon = "Volume2"
    name = "OpenAITTS"

    inputs = [
        SecretStrInput(name="api_key", display_name="OpenAI API Key", required=True),
        DropdownInput(
            name="model",
            display_name="Model",
            options=["tts-1", "tts-1-hd", "gpt-4o-mini-tts"],
            value="gpt-4o-mini-tts",
        ),
        DropdownInput(
            name="voice",
            display_name="Voice",
            options=["alloy", "echo", "fable", "onyx", "nova", "shimmer", "ash", "ballad", "coral", "sage", "verse"],
            value="alloy",
        ),
        IntInput(
            name="sample_rate",
            display_name="Sample Rate",
            value=24000,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="TTS",
            name="tts",
            method="build_service",
            types=["PipecatTTSService", "PipecatFrameProcessor"],
        ),
    ]

    def build_service(self) -> PipecatTTSService:
        from pipecat.services.openai.tts import OpenAITTSService

        return OpenAITTSService(
            api_key=self.api_key,
            model=self.model,
            voice=self.voice,
            sample_rate=int(self.sample_rate),
        )
