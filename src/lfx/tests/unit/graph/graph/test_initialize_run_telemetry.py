"""Serving-plane telemetry attribution: initialize_run surfaces the end user as the tracing label.

``graph.tracing_user_id`` is a SEPARATE label from the trace's primary ``user_id`` (which stays the
executing SID). On an identified serving run the graph carries ``end_user_id``; ``initialize_run``
fills ``tracing_user_id`` from it so providers can attribute the run to the end user. Editor /
anonymous / feature-off runs leave ``end_user_id`` None, so the label is untouched (strict BC).
"""

from uuid import uuid4

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


@pytest.mark.asyncio
async def test_end_user_fills_tracing_user_id() -> None:
    graph = _graph()
    tracer = _CapturingTracer()
    graph._tracing_service = tracer
    graph._tracing_service_initialized = True
    graph.end_user_id = "alice"

    await graph.initialize_run()

    assert graph.tracing_user_id == "alice"
    assert tracer.captured["tracing_user_id"] == "alice"
    # The primary trace attribution stays the executing SID, never the end user.
    assert tracer.captured["user_id"] == graph.user_id


@pytest.mark.asyncio
async def test_no_end_user_leaves_tracing_user_id_none() -> None:
    graph = _graph()
    tracer = _CapturingTracer()
    graph._tracing_service = tracer
    graph._tracing_service_initialized = True
    # end_user_id defaults None (editor / anonymous / feature-off)

    await graph.initialize_run()

    assert graph.tracing_user_id is None
    assert tracer.captured["tracing_user_id"] is None


@pytest.mark.asyncio
async def test_explicit_tracing_user_id_is_not_overridden() -> None:
    # A caller label already set (e.g. v1 input_request.user_id) wins over the end-user fill-in.
    graph = _graph()
    tracer = _CapturingTracer()
    graph._tracing_service = tracer
    graph._tracing_service_initialized = True
    graph.tracing_user_id = "caller-label"
    graph.end_user_id = "alice"

    await graph.initialize_run()

    assert graph.tracing_user_id == "caller-label"
