"""ElevenLabs text-to-speech service component."""

from lfx.base.pipecat.service import PipecatServiceComponent
from lfx.field_typing.voice_types import PipecatTTSService
from lfx.io import IntInput, Output, SecretStrInput, StrInput


class ElevenLabsTTSServiceComponent(PipecatServiceComponent):
    display_name = "ElevenLabs TTS"
    description = "Streaming text-to-speech via ElevenLabs."
    icon = "Volume2"
    name = "ElevenLabsTTS"

    inputs = [
        SecretStrInput(name="api_key", display_name="ElevenLabs API Key", required=True),
        StrInput(
            name="voice_id",
            display_name="Voice ID",
            required=True,
            info="ElevenLabs voice identifier (e.g. 'EXAVITQu4vr4xnSDxMaL').",
        ),
        StrInput(
            name="model",
            display_name="Model",
            value="eleven_turbo_v2_5",
            advanced=True,
        ),
        IntInput(
            name="sample_rate",
            display_name="Sample Rate",
            value=16000,
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
        from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

        return ElevenLabsTTSService(
            api_key=self.api_key,
            voice_id=self.voice_id,
            model=self.model,
            sample_rate=int(self.sample_rate),
        )
