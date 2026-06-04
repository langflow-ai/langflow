"""Stream-protocol adapters for the v2 workflows endpoint.

Each adapter translates Langflow ``EventManager`` events into a wire protocol's
SSE event bodies. Adapters register under a string name; the endpoint dispatches
by name based on the ``stream_protocol`` body field. Unknown protocols return
422 with the available list.

Adding a new protocol is one new module under ``adapters/`` plus one
``register_stream_adapter`` call. No endpoint changes.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel


@dataclass(frozen=True)
class StreamEvent:
    """One translated event ready to be wrapped in an SSE frame.

    ``type`` is the protocol-native event type string (e.g. ``"RUN_ERROR"``
    for AG-UI, ``"error"`` for langflow). The buffer task uses it to decide
    terminal job status. ``data_json`` is the already-serialized JSON string
    to place in the SSE ``data:`` field.
    """

    type: str
    data_json: str


class StreamAdapterContext(BaseModel):
    """Per-run context handed to an adapter at construction.

    Extensible: future adapters can need more fields. Add them here when a
    real adapter genuinely needs them, not speculatively.
    """

    run_id: str
    thread_id: str


@runtime_checkable
class StreamAdapter(Protocol):
    """The contract every stream adapter implements.

    Adapters are stateful per-run instances. The dispatcher calls
    ``initial_events`` once before draining the EventManager queue, then
    ``translate`` per event, then either ``final_events`` (clean end) or
    ``error_events`` (mid-stream failure). The caller frames the returned
    ``StreamEvent``s as SSE.
    """

    name: ClassVar[str]

    def initial_events(self) -> Iterable[StreamEvent]:
        """Events to emit before the run starts (e.g., ``RUN_STARTED``)."""

    def translate(self, event_type: str, event_data: dict[str, Any]) -> Iterable[StreamEvent]:
        """Translate one ``EventManager`` event into zero or more wire events."""

    def final_events(self) -> Iterable[StreamEvent]:
        """Events to emit after a clean end (e.g., ``RUN_FINISHED``)."""

    def error_events(self, error: BaseException) -> Iterable[StreamEvent]:
        """Events to emit when the run errors mid-stream."""

    @property
    def terminal_error_type(self) -> str | None:
        """Event-type the buffer task watches to flip a background job to FAILED.

        Returning ``None`` means the adapter never signals a terminal error
        via event type; the buffer task falls back to other signals.
        """

    def is_durable(self, event_type: str) -> bool:
        """True when a frame of ``event_type`` must be persisted to the durable log.

        Durable frames (milestones) are appended to ``job_events`` so a
        reattaching client can rebuild state after the live bus is gone.
        Ephemeral frames (token deltas) are published to the live bus only.
        Unknown types default to ephemeral — a new milestone must opt in
        explicitly rather than silently bloat the durable log.
        """


StreamAdapterFactory = Callable[[StreamAdapterContext], StreamAdapter]


class UnknownStreamProtocolError(LookupError):
    """Raised by ``get_stream_adapter`` when no adapter is registered under ``name``."""

    def __init__(self, name: str, available: list[str]) -> None:
        self.name = name
        self.available = available
        super().__init__(
            f"Unknown stream_protocol {name!r}; available: {available!r}",
        )


STREAM_ADAPTERS: dict[str, StreamAdapterFactory] = {}


def register_stream_adapter(name: str, factory: StreamAdapterFactory) -> None:
    """Register an adapter factory under ``name`` (idempotent overwrite)."""
    STREAM_ADAPTERS[name] = factory


def get_stream_adapter(name: str, context: StreamAdapterContext) -> StreamAdapter:
    """Build the adapter registered under ``name``; raise if unknown."""
    factory = STREAM_ADAPTERS.get(name)
    if factory is None:
        raise UnknownStreamProtocolError(name, available_protocols())
    return factory(context)


def available_protocols() -> list[str]:
    """Sorted list of registered protocol names. Drives the 422 error body."""
    return sorted(STREAM_ADAPTERS)


# Built-in adapter registrations happen here, after the registry is defined.
# Import for side-effect: each module calls ``register_stream_adapter``.
from langflow.api.v2.adapters import agui as _agui  # noqa: E402, F401
from langflow.api.v2.adapters import langflow as _langflow  # noqa: E402, F401
