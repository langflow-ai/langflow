"""Twilio telephony transport component.

Wraps ``FastAPIWebsocketTransport`` with ``TwilioFrameSerializer`` for Twilio
Media Streams. Pulls ``stream_sid`` / ``call_sid`` from the session context.
"""

from lfx.components.pipecat_transports._session import get_session, get_websocket
from lfx.custom.custom_component.component import Component
from lfx.field_typing.voice_types import PipecatTransport
from lfx.io import HandleInput, IntInput, Output, SecretStrInput


class TwilioTransportComponent(Component):
    display_name = "Twilio Transport"
    description = "Telephony transport for Twilio Media Streams."
    icon = "Phone"
    name = "TwilioTransport"
    category = "pipecat"

    inputs = [
        IntInput(name="audio_in_sample_rate", display_name="Input Sample Rate", value=8000, advanced=True),
        IntInput(name="audio_out_sample_rate", display_name="Output Sample Rate", value=8000, advanced=True),
        SecretStrInput(
            name="account_sid",
            display_name="Twilio Account SID",
            required=False,
            info="Optional; only needed if the serializer must call back to Twilio's API.",
            advanced=True,
        ),
        SecretStrInput(
            name="auth_token",
            display_name="Twilio Auth Token",
            required=False,
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
        from pipecat.serializers.twilio import TwilioFrameSerializer
        from pipecat.transports.websocket.fastapi import (
            FastAPIWebsocketParams,
            FastAPIWebsocketTransport,
        )

        websocket = get_websocket(self)
        session = get_session(self)
        stream_sid = session.get("stream_sid")
        call_sid = session.get("call_sid")
        if not stream_sid:
            msg = "TwilioTransport requires session_context['stream_sid'] from the connect handshake."
            raise RuntimeError(msg)

        serializer = TwilioFrameSerializer(
            stream_sid=stream_sid,
            call_sid=call_sid,
            account_sid=self.account_sid or None,
            auth_token=self.auth_token or None,
        )
        params = FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_sample_rate=int(self.audio_in_sample_rate),
            audio_out_sample_rate=int(self.audio_out_sample_rate),
            serializer=serializer,
            vad_analyzer=self.vad_analyzer,
        )
        return FastAPIWebsocketTransport(websocket=websocket, params=params)
