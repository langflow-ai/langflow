"""Exotel telephony transport component.

Wraps ``FastAPIWebsocketTransport`` with an ``ExotelFrameSerializer`` for
Exotel media streams (8 kHz mu-law). Pulls ``stream_sid`` / ``call_sid`` from
the session context populated by the API layer at WebSocket connect time.
"""

from lfx.components.pipecat_transports._session import get_session, get_websocket
from lfx.custom.custom_component.component import Component
from lfx.field_typing.voice_types import PipecatTransport
from lfx.io import HandleInput, IntInput, Output


class ExotelTransportComponent(Component):
    display_name = "Exotel Transport"
    description = "Telephony transport for Exotel media streams (8 kHz)."
    icon = "Phone"
    name = "ExotelTransport"
    category = "pipecat"

    inputs = [
        IntInput(
            name="audio_in_sample_rate",
            display_name="Input Sample Rate",
            value=8000,
            info="Exotel media streams are 8 kHz mu-law.",
            advanced=True,
        ),
        IntInput(
            name="audio_out_sample_rate",
            display_name="Output Sample Rate",
            value=8000,
            advanced=True,
        ),
        HandleInput(
            name="vad_analyzer",
            display_name="VAD Analyzer",
            input_types=["PipecatVADAnalyzer"],
            required=False,
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
        from pipecat.serializers.exotel import ExotelFrameSerializer
        from pipecat.transports.websocket.fastapi import (
            FastAPIWebsocketParams,
            FastAPIWebsocketTransport,
        )

        websocket = get_websocket(self)
        session = get_session(self)
        stream_sid = session.get("stream_sid")
        call_sid = session.get("call_sid")
        if not stream_sid:
            msg = "ExotelTransport requires session_context['stream_sid'] from the connect handshake."
            raise RuntimeError(msg)

        serializer = ExotelFrameSerializer(stream_sid=stream_sid, call_sid=call_sid)
        params = FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_sample_rate=int(self.audio_in_sample_rate),
            audio_out_sample_rate=int(self.audio_out_sample_rate),
            serializer=serializer,
            vad_analyzer=self.vad_analyzer,
        )
        return FastAPIWebsocketTransport(websocket=websocket, params=params)
