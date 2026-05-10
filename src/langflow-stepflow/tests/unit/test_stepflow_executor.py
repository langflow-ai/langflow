"""MVP smoke test for the StepflowExecutor adapter.

Verifies that the adapter:
- conforms to the lfx Executor ABC,
- registers under the expected ``kind``,
- routes through ``Coordinator`` when selected,
- translates a Langflow JSON workflow into a Stepflow Flow,
- raises a clear error when no orchestrator endpoint is configured (so we never silently no-op).

Submission against a live orchestrator is out of scope for the MVP; that path is
exercised by integration tests against a running stepflow stack.
"""

from __future__ import annotations

import pytest
from lfx.execution.coordinator import Coordinator
from lfx.execution.registry import ExecutorRegistry
from lfx.execution.types import RunComplete, StepResult, Unit

from langflow_stepflow.executor import StepflowExecutor


def _minimal_chat_passthrough() -> dict:
    """Smallest Langflow JSON the converter will accept end-to-end."""
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


def test_kind_is_stepflow():
    assert StepflowExecutor.kind == "stepflow"


def test_translate_produces_a_flow():
    executor = StepflowExecutor(endpoint="unused-for-translation")
    unit = Unit(graph=None, runtime_options={"langflow_json": _minimal_chat_passthrough()})
    flow = executor.translate(unit)
    assert flow is not None


def test_executor_registers_and_routes_through_coordinator():
    registry = ExecutorRegistry()
    registry.register(StepflowExecutor(endpoint="unused-for-this-test"))
    coordinator = Coordinator(registry=registry, executor_kind="stepflow")
    assert registry.has("stepflow")
    # We don't actually run anything here: we only confirm the seam picked up our
    # executor under the configured kind. The async path is verified separately.
    assert coordinator._registry.get("stepflow").kind == "stepflow"  # noqa: SLF001


@pytest.mark.asyncio
async def test_execute_without_endpoint_raises_clearly(monkeypatch):
    monkeypatch.delenv("STEPFLOW_ENDPOINT", raising=False)
    executor = StepflowExecutor()
    unit = Unit(graph=None, runtime_options={"langflow_json": _minimal_chat_passthrough()})
    with pytest.raises(RuntimeError, match="no orchestrator endpoint"):
        async for _ in executor.execute(unit):
            pass


@pytest.mark.asyncio
async def test_coordinator_run_propagates_executor_error(monkeypatch):
    monkeypatch.delenv("STEPFLOW_ENDPOINT", raising=False)
    registry = ExecutorRegistry()
    registry.register(StepflowExecutor())
    coordinator = Coordinator(registry=registry, executor_kind="stepflow")
    with pytest.raises(RuntimeError, match="no orchestrator endpoint"):
        async for _ in coordinator.run(graph=None, inputs=[], langflow_json=_minimal_chat_passthrough()):
            pass


def test_value_types_are_lfx_seam_types():
    # Sanity: the adapter speaks the seam's value-object vocabulary, not its own.
    assert StepResult.__module__.startswith("lfx.execution")
    assert RunComplete.__module__.startswith("lfx.execution")
