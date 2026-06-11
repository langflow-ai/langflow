"""FastAPI WebSocket transport component.

Wraps ``pipecat.transports.websocket.fastapi.FastAPIWebsocketTransport`` for
browser-facing voice agents communicating over raw PCM. The live ``WebSocket``
is pulled from the graph's session context (see ``_session.get_websocket``).
"""

from lfx.components.pipecat_transports._session import get_websocket
from lfx.custom.custom_component.component import Component
from lfx.field_typing.voice_types import PipecatTransport
from lfx.io import BoolInput, HandleInput, IntInput, Output


class FastAPIWebsocketTransportComponent(Component):
    display_name = "FastAPI WebSocket Transport"
    description = "Transport that streams raw audio over a FastAPI WebSocket (browser test client)."
    icon = "Mic"
    name = "FastAPIWebsocketTransport"
    category = "pipecat"

    inputs = [
        IntInput(
            name="audio_in_sample_rate",
            display_name="Input Sample Rate",
            value=16000,
            info="PCM sample rate expected from the client (Hz).",
        ),
        IntInput(
            name="audio_out_sample_rate",
            display_name="Output Sample Rate",
            value=16000,
            info="PCM sample rate sent to the client (Hz).",
        ),
        BoolInput(
            name="add_wav_header",
            display_name="Add WAV Header",
            value=False,
            info="Wrap each outbound chunk in a WAV header (some browser players require this).",
            advanced=True,
        ),
        HandleInput(
            name="vad_analyzer",
            display_name="VAD Analyzer",
            input_types=["PipecatVADAnalyzer"],
            required=False,
            info="Optional Silero/Krisp VAD analyzer to attach to the input transport.",
        ),
    ]

    outputs = [
        Output(
            display_name="Transport",
            name="transport",
            method="build_transport",
            types=["PipecatTransport"],
        ),
    ]

    def build_transport(self) -> PipecatTransport:
        from pipecat.transports.websocket.fastapi import (
            FastAPIWebsocketParams,
            FastAPIWebsocketTransport,
        )

        websocket = get_websocket(self)
        params = FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_sample_rate=int(self.audio_in_sample_rate),
            audio_out_sample_rate=int(self.audio_out_sample_rate),
            add_wav_header=bool(self.add_wav_header),
            vad_analyzer=self.vad_analyzer,
        )
        return FastAPIWebsocketTransport(websocket=websocket, params=params)
