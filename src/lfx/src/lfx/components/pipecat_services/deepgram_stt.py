"""Deepgram speech-to-text service component."""

from lfx.base.pipecat.service import PipecatServiceComponent
from lfx.field_typing.voice_types import PipecatSTTService
from lfx.io import IntInput, Output, SecretStrInput, StrInput


class DeepgramSTTServiceComponent(PipecatServiceComponent):
    display_name = "Deepgram STT"
    description = "Real-time speech-to-text via Deepgram."
    icon = "Mic"
    name = "DeepgramSTT"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Deepgram API Key",
            required=True,
        ),
        IntInput(
            name="sample_rate",
            display_name="Sample Rate",
            value=16000,
            advanced=True,
        ),
        StrInput(
            name="encoding",
            display_name="Encoding",
            value="linear16",
            info="Audio encoding (linear16, mulaw, etc.).",
            advanced=True,
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
        from pipecat.services.deepgram.stt import DeepgramSTTService

        return DeepgramSTTService(
            api_key=self.api_key,
            sample_rate=int(self.sample_rate),
            encoding=self.encoding,
        )
