import pytest
from lfx.execution.coordinator import Coordinator
from lfx.execution.registry import ExecutorRegistry
from lfx.execution.types import RunComplete, StepResult


def _make_coordinator():
    from lfx.execution.backends.in_process import InProcessExecutor

    registry = ExecutorRegistry()
    registry.register(InProcessExecutor())
    return Coordinator(registry=registry)


@pytest.mark.asyncio
async def test_run_yields_streaming_step_results_ending_in_run_complete(simple_graph):
    coordinator = _make_coordinator()
    items = [item async for item in coordinator.run(simple_graph, inputs=[{"input_value": "hi"}])]
    assert isinstance(items[-1], RunComplete)
    assert all(isinstance(i, StepResult) for i in items[:-1])


@pytest.mark.asyncio
async def test_run_to_completion_drains_and_returns_outputs(simple_graph):
    coordinator = _make_coordinator()
    outputs = await coordinator.run_to_completion(simple_graph, inputs=[{"input_value": "hi"}])
    assert isinstance(outputs, list)


@pytest.mark.asyncio
async def test_run_to_completion_propagates_executor_errors(simple_graph):
    coordinator = _make_coordinator()

    async def boom(*args, **kwargs):  # noqa: ARG001
        msg = "boom"
        raise RuntimeError(msg)

    simple_graph._arun_legacy = boom

    with pytest.raises(RuntimeError, match="boom"):
        await coordinator.run_to_completion(simple_graph, inputs=[{"input_value": "hi"}], _use_arun_legacy=True)


@pytest.mark.asyncio
async def test_run_with_no_executor_registered_raises(simple_graph):
    from lfx.execution.registry import ExecutorNotFoundError

    coordinator = Coordinator(registry=ExecutorRegistry())
    with pytest.raises(ExecutorNotFoundError):
        async for _ in coordinator.run(simple_graph, inputs=[]):
            pass


@pytest.mark.asyncio
async def test_stream_helper_yields_payloads_directly(simple_graph):
    coordinator = _make_coordinator()
    payloads = [p async for p in coordinator.stream(simple_graph, initial_inputs=None)]
    assert payloads
    assert any(hasattr(p, "vertex") for p in payloads)
