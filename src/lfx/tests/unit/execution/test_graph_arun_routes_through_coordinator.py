import asyncio

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.execution import (
    Coordinator,
    ExecutorRegistry,
    get_default_registry,
    set_default_coordinator,
)
from lfx.execution.executor import Executor
from lfx.execution.types import RunComplete
from lfx.graph import Graph
from lfx.graph.schema import RunOutputs


def _simple_graph():
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(should_store_message=False)
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(sender_name=chat_input.message_response)
    return Graph(chat_input, chat_output)


@pytest.mark.asyncio
async def test_arun_dispatches_through_coordinator():
    units_seen: list[object] = []

    class Recording(Executor):
        kind = "in-process"

        async def execute(self, unit):
            units_seen.append(unit)
            yield RunComplete(outputs=[])

    registry = ExecutorRegistry()
    registry.register(Recording())
    set_default_coordinator(Coordinator(registry=registry))

    await _simple_graph().arun(inputs=[{"input_value": "hi"}])
    assert len(units_seen) == 1


@pytest.mark.asyncio
async def test_arun_returns_run_outputs_shape():
    """Real graph through the default coordinator returns list[RunOutputs]."""
    # Touch the default registry to pre-warm; conftest resets between tests.
    assert get_default_registry().get("in-process").kind == "in-process"
    outputs = await _simple_graph().arun(inputs=[{"input_value": "hi"}])
    assert isinstance(outputs, list)
    assert len(outputs) == 1
    assert isinstance(outputs[0], RunOutputs)


@pytest.mark.asyncio
async def test_arun_handles_concurrent_calls_on_same_graph_instance():
    graph = _simple_graph()
    seen: list[str] = []

    async def patched(*, inputs, **kwargs):  # noqa: ARG001
        seen.append(kwargs.get("session_id") or "")
        await asyncio.sleep(0.01)
        return []

    graph._arun_legacy = patched

    await asyncio.gather(
        graph.arun(inputs=[{"input_value": "a"}], session_id="A"),
        graph.arun(inputs=[{"input_value": "b"}], session_id="B"),
    )
    assert sorted(seen) == ["A", "B"]
