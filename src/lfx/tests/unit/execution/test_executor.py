import pytest
from lfx.execution.executor import Executor
from lfx.execution.types import RunComplete, StepResult, Unit


def test_executor_is_abstract():
    with pytest.raises(TypeError, match="abstract"):
        Executor()


@pytest.mark.asyncio
async def test_concrete_executor_yields_steps_then_run_complete():
    class Toy(Executor):
        kind = "toy"

        async def execute(self, unit):  # noqa: ARG002
            yield StepResult(payload={"vertex_id": "a"})
            yield StepResult(payload={"vertex_id": "b"})
            yield RunComplete(outputs=["done"])

    items = [item async for item in Toy().execute(Unit(graph=object(), inputs=[]))]
    assert len(items) == 3
    assert isinstance(items[-1], RunComplete)
    assert items[-1].outputs == ["done"]


@pytest.mark.asyncio
async def test_executor_must_yield_run_complete_last():
    class Toy(Executor):
        kind = "toy"

        async def execute(self, unit):  # noqa: ARG002
            yield StepResult(payload={})
            yield RunComplete(outputs=[])

    items = [item async for item in Toy().execute(Unit(graph=object(), inputs=[]))]
    assert isinstance(items[-1], RunComplete)
