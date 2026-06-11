"""Pipecat transport components.

Transports adapt an external session (WebSocket, WebRTC room, telephony stream)
into the Pipecat frame pipeline. Each component outputs a live ``BaseTransport``
that the terminal ``VoicePipelineComponent`` wraps with ``transport.input()`` /
``transport.output()``.

The per-session ``WebSocket`` is injected by the API layer into the graph's
session context (Phase 6): ``graph.context["session"]``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from lfx.components.pipecat_transports.exotel_transport import ExotelTransportComponent
    from lfx.components.pipecat_transports.fastapi_websocket_transport import FastAPIWebsocketTransportComponent
    from lfx.components.pipecat_transports.twilio_transport import TwilioTransportComponent

_dynamic_imports = {
    "ExotelTransportComponent": "exotel_transport",
    "FastAPIWebsocketTransportComponent": "fastapi_websocket_transport",
    "TwilioTransportComponent": "twilio_transport",
}

__all__ = [
    "ExotelTransportComponent",
    "FastAPIWebsocketTransportComponent",
    "TwilioTransportComponent",
]


def __getattr__(attr_name: str) -> Any:
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
