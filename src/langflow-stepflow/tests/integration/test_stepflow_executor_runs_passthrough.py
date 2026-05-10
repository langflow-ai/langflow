"""End-to-end integration test for StepflowExecutor.

Boots a local Stepflow orchestrator, spawns the langflow worker, dispatches a
ChatInput->ChatOutput passthrough flow through the executor, and verifies the run
reaches a terminal SUCCEEDED status.

Skipped unless ``stepflow-py[local]`` and ``stepflow-orchestrator`` are installed --
this test depends on running a separate subprocess (the Rust orchestrator) and a
gRPC worker.
"""

from __future__ import annotations

import pytest
from lfx.execution.types import RunComplete, StepResult, Unit

from langflow_stepflow.executor import StepflowExecutor

pytestmark = pytest.mark.integration

# Skip the whole module if the local-orchestrator extra isn't installed.
pytest.importorskip("stepflow_py.config")


def _passthrough_flow() -> dict:
    return {
        "name": "passthrough",
        "data": {
            "nodes": [
                {
                    "id": "ChatInput-1",
                    "data": {
                        "type": "ChatInput",
                        "node": {"template": {"input_value": {"value": "hi"}}},
                    },
                },
                {
                    "id": "ChatOutput-1",
                    "data": {
                        "type": "ChatOutput",
                        "node": {"template": {"input_value": {}}},
                    },
                },
            ],
            "edges": [
                {
                    "source": "ChatInput-1",
                    "target": "ChatOutput-1",
                    "data": {
                        "sourceHandle": {"name": "message"},
                        "targetHandle": {"fieldName": "input_value"},
                    },
                }
            ],
        },
    }


# Stepflow ExecutionStatus enum: 2 == SUCCEEDED.
_SUCCEEDED = 2


@pytest.mark.asyncio
async def test_executor_runs_passthrough_end_to_end():
    executor = StepflowExecutor()
    unit = Unit(
        graph=None,
        inputs=[{"message": "hello world"}],
        runtime_options={"langflow_json": _passthrough_flow()},
    )

    events: list[object] = []
    completion: RunComplete | None = None
    async for item in executor.execute(unit):
        if isinstance(item, StepResult):
            events.append(item.payload)
        elif isinstance(item, RunComplete):
            completion = item

    assert completion is not None, "executor never yielded RunComplete"
    assert events, "executor yielded no step events"
    terminal = completion.outputs[-1]
    assert getattr(terminal, "status", None) == _SUCCEEDED, f"run did not succeed: {terminal!r}"
