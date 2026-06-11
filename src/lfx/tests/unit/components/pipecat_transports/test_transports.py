"""Tests for pipecat_transports components."""


def _transport_input_names(cls) -> set:
    return {i.name for i in cls.inputs}


def _transport_output_types(cls) -> set:
    return {t for o in cls.outputs for t in o.types}


class TestFastAPIWebsocketTransportComponent:
    """FastAPIWebsocketTransportComponent structure."""

    def test_metadata(self):
        from lfx.components.pipecat_transports.fastapi_websocket_transport import (
            FastAPIWebsocketTransportComponent,
        )

        assert FastAPIWebsocketTransportComponent.display_name == "FastAPI WebSocket Transport"
        assert FastAPIWebsocketTransportComponent.name == "FastAPIWebsocketTransport"
        assert FastAPIWebsocketTransportComponent.category == "pipecat"

    def test_output_type_is_transport(self):
        from lfx.components.pipecat_transports.fastapi_websocket_transport import (
            FastAPIWebsocketTransportComponent,
        )

        types = _transport_output_types(FastAPIWebsocketTransportComponent)
        assert "PipecatTransport" in types


class TestExotelTransportComponent:
    """ExotelTransportComponent structure."""

    def test_metadata(self):
        from lfx.components.pipecat_transports.exotel_transport import ExotelTransportComponent

        assert ExotelTransportComponent.display_name == "Exotel Transport"
        assert ExotelTransportComponent.name == "ExotelTransport"
        assert ExotelTransportComponent.category == "pipecat"

    def test_output_type_is_transport(self):
        from lfx.components.pipecat_transports.exotel_transport import ExotelTransportComponent

        types = _transport_output_types(ExotelTransportComponent)
        assert "PipecatTransport" in types


class TestTwilioTransportComponent:
    """TwilioTransportComponent structure."""

    def test_metadata(self):
        from lfx.components.pipecat_transports.twilio_transport import TwilioTransportComponent

        assert TwilioTransportComponent.display_name == "Twilio Transport"
        assert TwilioTransportComponent.name == "TwilioTransport"
        assert TwilioTransportComponent.category == "pipecat"

    def test_output_type_is_transport(self):
        from lfx.components.pipecat_transports.twilio_transport import TwilioTransportComponent

        types = _transport_output_types(TwilioTransportComponent)
        assert "PipecatTransport" in types
