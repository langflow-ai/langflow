"""Cartesia text-to-speech service component."""

from lfx.base.pipecat.service import PipecatServiceComponent
from lfx.field_typing.voice_types import PipecatTTSService
from lfx.io import IntInput, Output, SecretStrInput, StrInput


class CartesiaTTSServiceComponent(PipecatServiceComponent):
    display_name = "Cartesia TTS"
    description = "Streaming text-to-speech via Cartesia."
    icon = "Volume2"
    name = "CartesiaTTS"

    inputs = [
        SecretStrInput(name="api_key", display_name="Cartesia API Key", required=True),
        StrInput(
            name="voice_id",
            display_name="Voice ID",
            required=True,
            info="Cartesia voice identifier.",
        ),
        StrInput(
            name="model",
            display_name="Model",
            value="sonic-2",
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
        from pipecat.services.cartesia.tts import CartesiaTTSService

        sample_rate = int(self.sample_rate)
        if sample_rate <= 0:
            msg = f"sample_rate must be a positive integer, got {sample_rate}"
            raise ValueError(msg)
        return CartesiaTTSService(
            api_key=self.api_key,
            voice_id=self.voice_id,
            model=self.model,
            sample_rate=sample_rate,
        )
