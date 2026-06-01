r"""The ``langflow`` stream adapter: passthrough of EventManager events.

Wire shape: ``data: {"event": "<type>", "data": {...}}\n\n`` per SSE frame.
This is the same shape v1's ``build_flow`` already streams, so existing
clients (curl users, the v1 frontend) can read it without learning anything new.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any, ClassVar

from langflow.api.v2.adapters import (
    StreamAdapterContext,
    StreamEvent,
    register_stream_adapter,
)


class LangflowAdapter:
    """Passthrough adapter: each EventManager event becomes one wire event."""

    name: ClassVar[str] = "langflow"

    def __init__(self, context: StreamAdapterContext) -> None:
        self.context = context

    def initial_events(self) -> Iterable[StreamEvent]:
        return ()

    def translate(self, event_type: str, event_data: dict[str, Any]) -> Iterable[StreamEvent]:
        payload = {"event": event_type, "data": event_data}
        # ``default=str`` keeps non-JSON-serializable values (e.g. component
        # objects logged by add_message) from crashing the stream.
        return (StreamEvent(type=event_type, data_json=json.dumps(payload, default=str)),)

    def final_events(self) -> Iterable[StreamEvent]:
        return ()

    def error_events(self, error: BaseException) -> Iterable[StreamEvent]:
        payload = {"event": "error", "data": {"error": str(error)}}
        return (StreamEvent(type="error", data_json=json.dumps(payload)),)

    @property
    def terminal_error_type(self) -> str | None:
        return "error"


register_stream_adapter("langflow", LangflowAdapter)
