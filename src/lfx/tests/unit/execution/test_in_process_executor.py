import asyncio

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.events.event_manager import EventManager
from lfx.execution.backends.in_process import InProcessExecutor
from lfx.execution.types import RunComplete, StepResult, Unit
from lfx.graph import Graph


def _simple_graph():
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(should_store_message=False)
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(sender_name=chat_input.message_response)
    return Graph(chat_input, chat_output)


def test_in_process_executor_kind():
    assert InProcessExecutor().kind == "in-process"


@pytest.mark.asyncio
async def test_streams_step_results_then_run_complete_for_real_graph():
    """Streaming path: empty inputs forces async_start, multiple StepResults yielded."""
    from lfx.schema.schema import InputValueRequest

    graph = _simple_graph()
    unit = Unit(
        graph=graph,
        inputs=[],
        runtime_options={"initial_inputs": InputValueRequest(input_value="hello")},
    )

    items = [item async for item in InProcessExecutor().execute(unit)]

    assert isinstance(items[-1], RunComplete)
    assert all(isinstance(i, StepResult) for i in items[:-1])
    assert len(items) >= 2


@pytest.mark.asyncio
async def test_run_complete_outputs_match_arun_shape():
    """Legacy path: dict inputs + flag yields list[RunOutputs] from _arun_legacy."""
    from lfx.graph.schema import RunOutputs

    graph = _simple_graph()
    unit = Unit(
        graph=graph,
        inputs=[{"input_value": "hello world"}],
        runtime_options={"_use_arun_legacy": True},
    )

    items = [item async for item in InProcessExecutor().execute(unit)]
    rc = items[-1]
    assert isinstance(rc, RunComplete)
    assert len(rc.outputs) == 1
    assert isinstance(rc.outputs[0], RunOutputs)


@pytest.mark.asyncio
async def test_event_manager_in_runtime_options_is_used():
    """Streaming path forwards event_manager into async_start so vertex events fire."""
    from lfx.schema.schema import InputValueRequest

    graph = _simple_graph()
    queue: asyncio.Queue = asyncio.Queue()
    em = EventManager(queue=queue)

    seen: list[str] = []

    def record(*, manager, event_type, data):  # noqa: ARG001
        seen.append(f"{event_type}:{data.get('id') if isinstance(data, dict) else ''}")

    em.register_event("on_build_start", "build_start", record)

    unit = Unit(
        graph=graph,
        inputs=[],
        runtime_options={
            "event_manager": em,
            "initial_inputs": InputValueRequest(input_value="hi"),
        },
    )
    [_ async for _ in InProcessExecutor().execute(unit)]

    assert any(s.startswith("build_start:chat_input") for s in seen)


@pytest.mark.asyncio
async def test_propagates_graph_errors():
    graph = _simple_graph()

    async def boom(*args, **kwargs):  # noqa: ARG001
        msg = "boom"
        raise RuntimeError(msg)

    graph._arun_legacy = boom

    unit = Unit(graph=graph, inputs=[{}], runtime_options={"_use_arun_legacy": True})
    with pytest.raises(RuntimeError, match="boom"):
        async for _ in InProcessExecutor().execute(unit):
            pass


@pytest.mark.asyncio
async def test_concurrent_runs_on_separate_graphs_keep_runtime_options_isolated():
    """Concurrent executor calls on separate Graph instances must each see their own options.

    Same-instance concurrency is unsafe due to shared state mutations inside _arun_legacy
    (self.session_id and others); the seam doesn't promise to fix that. Separate instances,
    however, must remain isolated through the executor layer.
    """
    seen: list[str | None] = []

    async def patched_arun_legacy(*, inputs, **kwargs):  # noqa: ARG001
        seen.append(kwargs.get("session_id"))
        await asyncio.sleep(0.01)
        return []

    async def run_with(session_id):
        graph = _simple_graph()
        graph._arun_legacy = patched_arun_legacy
        unit = Unit(
            graph=graph,
            inputs=[{}],
            runtime_options={"session_id": session_id, "_use_arun_legacy": True},
        )
        [_ async for _ in InProcessExecutor().execute(unit)]

    await asyncio.gather(run_with("A"), run_with("B"))
    assert sorted(seen) == ["A", "B"]
