"""The ``agui`` stream adapter: wraps ``AGUITranslator`` for the registry.

Frames each AG-UI ``BaseEvent`` as JSON via ``model_dump_json(by_alias=True,
exclude_none=True)`` so the wire shape stays camelCase and omits unset fields.
Per-run state lives on the wrapped translator instance.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, ClassVar

from ag_ui.core import BaseEvent, RunErrorEvent

from langflow.api.v2.adapters import (
    StreamAdapterContext,
    StreamEvent,
    register_stream_adapter,
)
from langflow.api.v2.agui_translator import AGUITranslator

# Durable AG-UI milestones. ``TEXT_MESSAGE_CONTENT`` is the per-token delta and
# is ephemeral; the START/END lifecycle frames around it are durable so a
# reattaching client knows a message happened even without the token stream.
_AGUI_DURABLE_EVENTS: frozenset[str] = frozenset(
    {
        "RUN_STARTED",
        "RUN_FINISHED",
        "RUN_ERROR",
        "STEP_STARTED",
        "STEP_FINISHED",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_END",
        "TOOL_CALL_START",
        "TOOL_CALL_ARGS",
        "TOOL_CALL_END",
        "STATE_SNAPSHOT",
        "STATE_DELTA",
        "CUSTOM",
    }
)


def _to_stream_event(event: BaseEvent) -> StreamEvent:
    """Frame one AG-UI event for SSE consumption."""
    type_attr = event.type
    type_str = type_attr.value if hasattr(type_attr, "value") else str(type_attr)
    return StreamEvent(
        type=type_str,
        data_json=event.model_dump_json(by_alias=True, exclude_none=True),
    )


class AGUIAdapter:
    """Wraps ``AGUITranslator``; one instance per run."""

    name: ClassVar[str] = "agui"

    def __init__(self, context: StreamAdapterContext) -> None:
        self.context = context
        self._translator = AGUITranslator(
            run_id=context.run_id,
            thread_id=context.thread_id,
        )

    def initial_events(self) -> Iterable[StreamEvent]:
        return [_to_stream_event(e) for e in self._translator.start()]

    def translate(self, event_type: str, event_data: dict[str, Any]) -> Iterable[StreamEvent]:
        return [_to_stream_event(e) for e in self._translator.translate(event_type, event_data)]

    def final_events(self) -> Iterable[StreamEvent]:
        # RUN_FINISHED rides on the translator's ``end`` translation; no extra
        # framing is emitted here. Present so ``StreamAdapter`` is satisfied.
        return ()

    def error_events(self, error: BaseException) -> Iterable[StreamEvent]:
        # Fallback path: emitted by the dispatcher when on_error itself fails
        # or when no error event has reached the translator.
        return [_to_stream_event(RunErrorEvent(message=str(error)))]

    @property
    def terminal_error_type(self) -> str | None:
        return "RUN_ERROR"

    def is_durable(self, event_type: str) -> bool:
        return event_type in _AGUI_DURABLE_EVENTS


register_stream_adapter("agui", AGUIAdapter)
