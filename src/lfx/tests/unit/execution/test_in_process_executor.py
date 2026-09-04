import asyncio

import pytest
from lfx.events.event_manager import EventManager
from lfx.execution.backends.in_process import InProcessExecutor
from lfx.execution.types import RunComplete, StepResult, Unit


def test_in_process_executor_kind():
    assert InProcessExecutor().kind == "in-process"


@pytest.mark.asyncio
async def test_streams_step_results_then_run_complete_for_real_graph(simple_graph):
    """Streaming path emits StepResult per vertex build plus a Finish step, then RunComplete."""
    from lfx.graph.graph.constants import Finish
    from lfx.schema.schema import InputValueRequest

    unit = Unit(
        graph=simple_graph,
        inputs=[],
        runtime_options={"initial_inputs": InputValueRequest(input_value="hello world")},
    )

    items = [item async for item in InProcessExecutor().execute(unit)]
    step_payloads = [i.payload for i in items if isinstance(i, StepResult)]

    assert isinstance(items[-1], RunComplete)
    assert all(isinstance(i, StepResult) for i in items[:-1])
    vertex_ids = [getattr(p, "vertex", None) and p.vertex.id for p in step_payloads]
    assert "chat_input" in vertex_ids
    assert "chat_output" in vertex_ids
    assert any(isinstance(p, Finish) for p in step_payloads)


@pytest.mark.asyncio
async def test_run_complete_outputs_match_arun_shape(simple_graph):
    """Legacy path: dict inputs + flag yields list[RunOutputs] from _arun_legacy."""
    from lfx.graph.schema import RunOutputs

    unit = Unit(
        graph=simple_graph,
        inputs=[{"input_value": "hello world"}],
        runtime_options={"_use_arun_legacy": True},
    )

    items = [item async for item in InProcessExecutor().execute(unit)]
    rc = items[-1]
    assert isinstance(rc, RunComplete)
    assert len(rc.outputs) == 1
    assert isinstance(rc.outputs[0], RunOutputs)
    assert rc.outputs[0].inputs == {"input_value": "hello world"}


@pytest.mark.asyncio
async def test_event_manager_in_runtime_options_is_used(simple_graph):
    """Streaming path forwards event_manager into async_start so vertex events fire."""
    from lfx.schema.schema import InputValueRequest

    queue: asyncio.Queue = asyncio.Queue()
    em = EventManager(queue=queue)

    seen: list[str] = []

    def record(*, manager, event_type, data):  # noqa: ARG001
        seen.append(f"{event_type}:{data.get('id') if isinstance(data, dict) else ''}")

    em.register_event("on_build_start", "build_start", record)

    unit = Unit(
        graph=simple_graph,
        inputs=[],
        runtime_options={
            "event_manager": em,
            "initial_inputs": InputValueRequest(input_value="hi"),
        },
    )
    [_ async for _ in InProcessExecutor().execute(unit)]

    assert any(s.startswith("build_start:chat_input") for s in seen)
    assert any(s.startswith("build_start:chat_output") for s in seen)


@pytest.mark.asyncio
async def test_propagates_graph_errors(simple_graph):
    async def boom(*args, **kwargs):  # noqa: ARG001
        msg = "boom"
        raise RuntimeError(msg)

    simple_graph._arun_legacy = boom

    unit = Unit(graph=simple_graph, inputs=[{}], runtime_options={"_use_arun_legacy": True})
    with pytest.raises(RuntimeError, match="boom"):
        async for _ in InProcessExecutor().execute(unit):
            pass


@pytest.mark.asyncio
async def test_fallback_to_env_vars_forwarded_in_streaming_path():
    """Regression: the streaming path must forward fallback_to_env_vars to async_start."""

    class _Stub:
        seen_fallback: bool | None = None

        async def async_start(self, **kwargs):
            _Stub.seen_fallback = kwargs.get("fallback_to_env_vars")
            return
            yield

    unit = Unit(graph=_Stub(), inputs=[], runtime_options={"fallback_to_env_vars": True})
    [_ async for _ in InProcessExecutor().execute(unit)]
    assert _Stub.seen_fallback is True


@pytest.mark.asyncio
async def test_concurrent_runs_on_separate_graphs_keep_runtime_options_isolated():
    """Separate Graph instances stay isolated through the executor layer."""
    from lfx.components.input_output import ChatInput, ChatOutput
    from lfx.graph import Graph

    seen: list[str | None] = []

    async def patched_arun_legacy(*, inputs, **kwargs):  # noqa: ARG001
        seen.append(kwargs.get("session_id"))
        await asyncio.sleep(0.01)
        return []

    def _build():
        ci = ChatInput(_id="chat_input")
        ci.set(should_store_message=False)
        co = ChatOutput(input_value="test", _id="chat_output")
        co.set(sender_name=ci.message_response)
        g = Graph(ci, co)
        g._arun_legacy = patched_arun_legacy
        return g

    async def run_with(session_id):
        unit = Unit(
            graph=_build(),
            inputs=[{}],
            runtime_options={"session_id": session_id, "_use_arun_legacy": True},
        )
        [_ async for _ in InProcessExecutor().execute(unit)]

    await asyncio.gather(run_with("A"), run_with("B"))
    assert sorted(seen) == ["A", "B"]
