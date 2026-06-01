"""Contract tests for the stream-adapter registry.

The registry pattern lets us add new wire protocols (AG-UI, OpenAI Responses,
Vercel AI SDK, ...) without changing the v2 workflows endpoint. Each adapter
registers under a string name; the endpoint dispatches by name and returns
422 with the available list on unknown values.
"""

from __future__ import annotations

import pytest
from langflow.api.v2.adapters import (
    STREAM_ADAPTERS,
    StreamAdapterContext,
    StreamEvent,
    UnknownStreamProtocolError,
    available_protocols,
    get_stream_adapter,
    register_stream_adapter,
)


@pytest.fixture
def isolated_registry():
    """Snapshot and restore ``STREAM_ADAPTERS`` so tests don't leak registrations."""
    snapshot = dict(STREAM_ADAPTERS)
    try:
        yield STREAM_ADAPTERS
    finally:
        STREAM_ADAPTERS.clear()
        STREAM_ADAPTERS.update(snapshot)


def _ctx() -> StreamAdapterContext:
    return StreamAdapterContext(run_id="run-1", thread_id="thread-1")


class _NoopAdapter:
    """Minimal adapter implementing the Protocol surface."""

    name = "noop"

    def __init__(self, context: StreamAdapterContext) -> None:
        self.context = context

    def initial_events(self):
        return []

    def translate(self, event_type, _event_data):
        return [StreamEvent(type=event_type, data_json="{}")]

    def final_events(self):
        return []

    def error_events(self, _error):
        return []

    @property
    def terminal_error_type(self):
        return None


class TestBuiltinProtocols:
    """The built-in adapters are registered at import time."""

    def test_langflow_protocol_is_available_by_default(self):
        assert "langflow" in available_protocols()

    def test_agui_protocol_is_available_by_default(self):
        assert "agui" in available_protocols()


class TestRegistration:
    """Registering a new protocol makes it available via lookup."""

    def test_registered_adapter_can_be_resolved(self, isolated_registry):  # noqa: ARG002 — fixture used for snapshot/restore side effect
        register_stream_adapter("noop", _NoopAdapter)

        adapter = get_stream_adapter("noop", _ctx())

        assert isinstance(adapter, _NoopAdapter)
        assert adapter.context.run_id == "run-1"
        assert adapter.context.thread_id == "thread-1"

    def test_available_protocols_includes_new_registration(self, isolated_registry):  # noqa: ARG002 — fixture used for snapshot/restore side effect
        register_stream_adapter("noop", _NoopAdapter)
        assert "noop" in available_protocols()

    def test_available_protocols_is_sorted(self, isolated_registry):  # noqa: ARG002 — fixture used for snapshot/restore side effect
        register_stream_adapter("zzz-last", _NoopAdapter)
        register_stream_adapter("aaa-first", _NoopAdapter)
        names = available_protocols()
        assert names == sorted(names)


class TestUnknownProtocol:
    """Looking up an unknown protocol raises with the available list."""

    def test_unknown_protocol_raises_with_available_list(self, isolated_registry):  # noqa: ARG002 — fixture used for snapshot/restore side effect
        with pytest.raises(UnknownStreamProtocolError) as exc:
            get_stream_adapter("nonexistent", _ctx())

        assert exc.value.name == "nonexistent"
        assert "langflow" in exc.value.available
        # The error should be inspectable; the string form should mention both
        # the unknown name and the available names so a 422 detail can include them.
        msg = str(exc.value)
        assert "nonexistent" in msg
        assert "langflow" in msg


class TestStreamEvent:
    """``StreamEvent`` is the contract between adapter and SSE framer."""

    def test_stream_event_is_immutable(self):
        evt = StreamEvent(type="token", data_json='{"event":"token"}')
        with pytest.raises((AttributeError, TypeError, Exception)):
            evt.type = "other"  # type: ignore[misc]

    def test_stream_event_carries_type_and_serialized_data(self):
        evt = StreamEvent(type="RUN_STARTED", data_json='{"type":"RUN_STARTED"}')
        assert evt.type == "RUN_STARTED"
        assert evt.data_json == '{"type":"RUN_STARTED"}'
