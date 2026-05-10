"""Unit smoke tests for the StepflowExecutor adapter.

Covers wiring against the lfx execution seam: ABC conformance, registration, default
config shape, and translation. The actual orchestrator run is exercised by the
integration test in ``tests/integration/test_stepflow_executor_runs_passthrough.py``.
"""

from __future__ import annotations

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
    executor = StepflowExecutor()
    unit = Unit(graph=None, runtime_options={"langflow_json": _minimal_chat_passthrough()})
    flow = executor.translate(unit)
    assert flow is not None


def test_executor_registers_and_routes_through_coordinator():
    registry = ExecutorRegistry()
    registry.register(StepflowExecutor())
    coordinator = Coordinator(registry=registry, executor_kind="stepflow")
    assert registry.has("stepflow")
    assert coordinator._registry.get("stepflow").kind == "stepflow"  # noqa: SLF001


def test_default_config_registers_langflow_worker():
    # Verifies the default StepflowConfig is the one we'd need to actually route
    # /langflow/* steps to a worker -- the routing miss I hit during the first manual
    # run attempt should now be impossible with the defaults.
    executor = StepflowExecutor()
    config = executor._default_config()  # noqa: SLF001
    assert "langflow" in config.plugins
    assert "/langflow" in config.routes
    plugin_for_langflow = config.routes["/langflow"][0].plugin
    assert plugin_for_langflow == "langflow"
    # Default worker command should be invokable as a python module path.
    cmd, args = executor._worker_invocation()  # noqa: SLF001
    assert "langflow_stepflow.worker" in " ".join([cmd, *args])


def test_value_types_are_lfx_seam_types():
    assert StepResult.__module__.startswith("lfx.execution")
    assert RunComplete.__module__.startswith("lfx.execution")
