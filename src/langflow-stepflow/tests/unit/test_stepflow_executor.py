"""Unit smoke tests for the StepflowExecutor adapter.

Covers wiring against the lfx execution seam: ABC conformance, registration, default
config shape, and translation. The actual orchestrator run is exercised by the
integration test in ``tests/integration/test_stepflow_executor_runs_passthrough.py``.
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


# --- P1-a / P1-c: run-input mapping (lfx contract shape -> stepflow $.message/$.session_id) ---


def test_build_run_input_maps_input_field_to_message():
    executor = StepflowExecutor()
    unit = Unit(graph=None, inputs=[{"input_value": "hello"}], runtime_options={"session_id": "s1"})
    payload = executor._build_run_input(unit, 0)  # noqa: SLF001
    assert payload["message"] == "hello"
    assert payload["session_id"] == "s1"
    assert "input_value" not in payload


def test_build_run_input_defaults_session_id_to_empty_string():
    executor = StepflowExecutor()
    unit = Unit(graph=None, inputs=[{"input_value": "hi"}], runtime_options={})
    payload = executor._build_run_input(unit, 0)  # noqa: SLF001
    assert payload["session_id"] == ""


def test_build_run_input_preserves_extra_keys():
    executor = StepflowExecutor()
    unit = Unit(graph=None, inputs=[{"input_value": "hi", "foo": "bar"}], runtime_options={})
    payload = executor._build_run_input(unit, 0)  # noqa: SLF001
    assert payload["foo"] == "bar"
    assert payload["message"] == "hi"


def test_build_run_input_handles_no_inputs():
    executor = StepflowExecutor()
    unit = Unit(graph=None, inputs=[], runtime_options={})
    payload = executor._build_run_input(unit, 0)  # noqa: SLF001
    assert payload == {"session_id": ""}


# --- P1-b: terminal item result (protobuf Value) -> list[RunOutputs] ---


def _string_value(text: str):
    from google.protobuf import struct_pb2

    return struct_pb2.Value(string_value=text)


def _struct_value(data: dict):
    from google.protobuf import struct_pb2

    struct = struct_pb2.Struct()
    struct.update(data)
    return struct_pb2.Value(struct_value=struct)


def test_to_run_outputs_returns_run_outputs_contract():
    from lfx.graph.schema import ResultData, RunOutputs

    run_outputs = StepflowExecutor._to_run_outputs(_string_value("hello world"), {"input_value": "hello world"})  # noqa: SLF001
    assert isinstance(run_outputs, RunOutputs)
    assert run_outputs.inputs == {"input_value": "hello world"}
    assert len(run_outputs.outputs) == 1
    assert isinstance(run_outputs.outputs[0], ResultData)


def test_to_run_outputs_surfaces_string_message():
    run_outputs = StepflowExecutor._to_run_outputs(_string_value("hello world"), {"input_value": "x"})  # noqa: SLF001
    result_data = run_outputs.outputs[0]
    assert result_data.outputs["message"].message == "hello world"
    assert result_data.messages[0].message == "hello world"


def test_to_run_outputs_extracts_text_from_struct():
    run_outputs = StepflowExecutor._to_run_outputs(_struct_value({"text": "hi there", "sender": "AI"}), {})  # noqa: SLF001
    result_data = run_outputs.outputs[0]
    assert result_data.messages[0].message == "hi there"
    assert result_data.results["message"] == {"text": "hi there", "sender": "AI"}


def test_to_run_outputs_handles_missing_result():
    run_outputs = StepflowExecutor._to_run_outputs(None, {"input_value": "x"})  # noqa: SLF001
    assert run_outputs.outputs[0].messages == []


# --- terminal run status handling: a failed/cancelled run must fail loud, not look empty ---


def _status(name: str) -> int:
    from stepflow_py.proto import common_pb2

    return common_pb2.ExecutionStatus.Value(name)


def test_raise_for_failed_status_allows_completed():
    # Should not raise on a successful run.
    StepflowExecutor._raise_for_failed_status(_status("EXECUTION_STATUS_COMPLETED"), "run-1")  # noqa: SLF001


def test_raise_for_failed_status_allows_none():
    # A stream that ended without a terminal status is left to the coordinator, not raised here.
    StepflowExecutor._raise_for_failed_status(None, "run-1")  # noqa: SLF001


def test_raise_for_failed_status_raises_on_failed():
    from langflow_stepflow.exceptions import ExecutionError

    with pytest.raises(ExecutionError, match="non-success status: EXECUTION_STATUS_FAILED"):
        StepflowExecutor._raise_for_failed_status(_status("EXECUTION_STATUS_FAILED"), "run-1")  # noqa: SLF001


def test_raise_for_failed_status_raises_on_cancelled():
    from langflow_stepflow.exceptions import ExecutionError

    with pytest.raises(ExecutionError):
        StepflowExecutor._raise_for_failed_status(_status("EXECUTION_STATUS_CANCELLED"), "run-1")  # noqa: SLF001
