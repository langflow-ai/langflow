r"""The ``langflow`` stream adapter: passthrough of EventManager events.

Wire shape: ``data: {"event": "<type>", "data": {...}}\n\n`` per SSE frame.
This is the same shape v1's ``build_flow`` already streams, so existing
clients (curl users, the v1 frontend) can read it without learning anything new.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any, ClassVar

from lfx.schema.workflow import OutputEvent

from langflow.api.v2.adapters import (
    StreamAdapterContext,
    StreamEvent,
    register_stream_adapter,
)
from langflow.api.v2.converters import build_component_output, resolve_output_type

# Durable milestones for the langflow wire protocol. ``token`` is the only
# high-volume ephemeral type; everything else the build loop emits is a
# milestone worth persisting for reattach.
_LANGFLOW_DURABLE_EVENTS: frozenset[str] = frozenset(
    {
        "build_start",
        "build_end",
        "vertices_sorted",
        "end_vertex",
        "output",
        "add_message",
        "remove_message",
        "error",
        "end",
    }
)


class LangflowAdapter:
    """Passthrough adapter: each EventManager event becomes one wire event.

    On a terminal ``end_vertex`` it ALSO emits a normalized ``output`` event whose
    payload is an :class:`OutputEvent` carrying the same ``ComponentOutput`` shape
    sync returns in ``outputs[id]``. That gives sync and the stream one parser: read
    ``type``/``status``/``display_name``/``content``/``metadata`` off both.
    """

    name: ClassVar[str] = "langflow"

    def __init__(self, context: StreamAdapterContext) -> None:
        self.context = context

    def initial_events(self) -> Iterable[StreamEvent]:
        return ()

    def translate(self, event_type: str, event_data: dict[str, Any]) -> Iterable[StreamEvent]:
        events = [self._passthrough(event_type, event_data)]
        if event_type == "end_vertex":
            output_event = self._output_event(event_data)
            if output_event is not None:
                events.append(output_event)
        return events

    @staticmethod
    def _passthrough(event_type: str, event_data: dict[str, Any]) -> StreamEvent:
        payload = {"event": event_type, "data": event_data}
        # ``default=str`` keeps non-JSON-serializable values (e.g. component
        # objects logged by add_message) from crashing the stream.
        return StreamEvent(type=event_type, data_json=json.dumps(payload, default=str))

    @staticmethod
    def _output_event(event_data: dict[str, Any]) -> StreamEvent | None:
        """Build the normalized ``output`` event for a terminal output, or None.

        Returns None for non-terminal vertices so the stream emits an ``output`` for
        exactly the set sync reports in ``outputs``. The vertex metadata is the
        authoritative ``output_meta`` shipped by the v1 build path.
        """
        output_meta = event_data.get("output_meta") or {}
        if not output_meta.get("is_terminal"):
            return None
        build_data = event_data.get("build_data") or {}
        component_id = output_meta.get("component_id") or build_data.get("id")
        if not component_id:
            return None
        component_output = build_component_output(
            component_id=component_id,
            is_output=bool(output_meta.get("is_output")),
            vertex_type=output_meta.get("vertex_type"),
            output_type=resolve_output_type(output_meta.get("output_types"), output_meta.get("vertex_type")),
            display_name=output_meta.get("display_name"),
            result_data=build_data.get("data"),
        )
        output = OutputEvent(component_id=component_id, **component_output.model_dump())
        payload = {"event": "output", "data": output.model_dump(mode="json")}
        return StreamEvent(type="output", data_json=json.dumps(payload, default=str))

    def final_events(self) -> Iterable[StreamEvent]:
        return ()

    def error_events(self, error: BaseException) -> Iterable[StreamEvent]:
        payload = {"event": "error", "data": {"error": str(error)}}
        return (StreamEvent(type="error", data_json=json.dumps(payload)),)

    @property
    def terminal_error_type(self) -> str | None:
        return "error"

    def is_durable(self, event_type: str) -> bool:
        return event_type in _LANGFLOW_DURABLE_EVENTS


register_stream_adapter("langflow", LangflowAdapter)
