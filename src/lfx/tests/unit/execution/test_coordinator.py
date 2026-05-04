import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.execution.coordinator import Coordinator
from lfx.execution.registry import ExecutorRegistry
from lfx.execution.types import RunComplete, StepResult
from lfx.graph import Graph


def _simple_graph():
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(should_store_message=False)
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(sender_name=chat_input.message_response)
    return Graph(chat_input, chat_output)


def _make_coordinator():
    from lfx.execution.backends.in_process import InProcessExecutor

    registry = ExecutorRegistry()
    registry.register(InProcessExecutor())
    return Coordinator(registry=registry)


@pytest.mark.asyncio
async def test_run_yields_streaming_step_results_ending_in_run_complete():
    coordinator = _make_coordinator()
    items = [item async for item in coordinator.run(_simple_graph(), inputs=[{"input_value": "hi"}])]
    assert isinstance(items[-1], RunComplete)
    assert all(isinstance(i, StepResult) for i in items[:-1])


@pytest.mark.asyncio
async def test_run_to_completion_drains_and_returns_outputs():
    coordinator = _make_coordinator()
    outputs = await coordinator.run_to_completion(_simple_graph(), inputs=[{"input_value": "hi"}])
    assert isinstance(outputs, list)


@pytest.mark.asyncio
async def test_run_to_completion_propagates_executor_errors():
    coordinator = _make_coordinator()
    graph = _simple_graph()

    async def boom(*args, **kwargs):  # noqa: ARG001
        msg = "boom"
        raise RuntimeError(msg)

    graph._arun_legacy = boom

    with pytest.raises(RuntimeError, match="boom"):
        await coordinator.run_to_completion(graph, inputs=[{"input_value": "hi"}], _use_arun_legacy=True)


@pytest.mark.asyncio
async def test_run_with_no_executor_registered_raises():
    from lfx.execution.registry import ExecutorNotFoundError

    coordinator = Coordinator(registry=ExecutorRegistry())
    with pytest.raises(ExecutorNotFoundError):
        async for _ in coordinator.run(_simple_graph(), inputs=[]):
            pass
