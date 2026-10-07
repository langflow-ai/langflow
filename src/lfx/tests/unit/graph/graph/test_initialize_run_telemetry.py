"""Serving-plane telemetry attribution: initialize_run surfaces the end user as the tracing label.

``graph.tracing_user_id`` is a SEPARATE label from the trace's primary ``user_id`` (which stays the
executing SID). The end-user id is PII, so forwarding it to the (third-party) tracing provider is
gated behind ``serving_trace_end_user`` and OFF by default (I4). When the operator opts in, an
identified serving run's ``end_user_id`` fills ``tracing_user_id``; otherwise the label is untouched.
"""

from uuid import uuid4

import lfx.graph.graph.base as base_module
import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.graph.base import Graph


class _CapturingTracer:
    """Minimal tracing service capturing the kwargs initialize_run passes to start_tracers."""

    def __init__(self) -> None:
        self.captured: dict = {}

    async def start_tracers(self, **kwargs) -> None:
        self.captured.update(kwargs)


def _graph() -> Graph:
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(input_value="hi")
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=chat_input.message_response)
    return Graph(chat_input, chat_output, flow_id=str(uuid4()), user_id=str(uuid4()))


def _with_tracer(graph: Graph) -> _CapturingTracer:
    tracer = _CapturingTracer()
    graph._tracing_service = tracer
    graph._tracing_service_initialized = True
    return tracer


def _enable_forwarding(monkeypatch, *, enabled: bool) -> None:
    monkeypatch.setattr(base_module, "_serving_trace_end_user_enabled", lambda: enabled)


@pytest.mark.asyncio
async def test_end_user_fills_tracing_user_id_when_opted_in(monkeypatch) -> None:
    _enable_forwarding(monkeypatch, enabled=True)
    graph = _graph()
    tracer = _with_tracer(graph)
    graph.end_user_id = "alice"

    await graph.initialize_run()

    assert graph.tracing_user_id == "alice"
    assert tracer.captured["tracing_user_id"] == "alice"
    # The primary trace attribution stays the executing SID, never the end user.
    assert tracer.captured["user_id"] == graph.user_id


@pytest.mark.asyncio
async def test_gate_off_by_default_does_not_forward_end_user(monkeypatch) -> None:
    # Default (operator has not opted in): the end user is NOT sent to the tracing provider.
    _enable_forwarding(monkeypatch, enabled=False)
    graph = _graph()
    tracer = _with_tracer(graph)
    graph.end_user_id = "alice"

    await graph.initialize_run()

    assert graph.tracing_user_id is None
    assert tracer.captured["tracing_user_id"] is None


@pytest.mark.asyncio
async def test_no_end_user_leaves_tracing_user_id_none(monkeypatch) -> None:
    _enable_forwarding(monkeypatch, enabled=True)
    graph = _graph()
    tracer = _with_tracer(graph)
    # end_user_id defaults None (editor / anonymous / feature-off)

    await graph.initialize_run()

    assert graph.tracing_user_id is None
    assert tracer.captured["tracing_user_id"] is None


@pytest.mark.asyncio
async def test_explicit_tracing_user_id_is_not_overridden(monkeypatch) -> None:
    # A caller label already set (e.g. v1 input_request.user_id) wins over the end-user fill-in.
    _enable_forwarding(monkeypatch, enabled=True)
    graph = _graph()
    _with_tracer(graph)
    graph.tracing_user_id = "caller-label"
    graph.end_user_id = "alice"

    await graph.initialize_run()

    assert graph.tracing_user_id == "caller-label"
