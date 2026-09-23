"""Execution path validation using test data flows.

This test validates that both execution paths produce identical results
using the test flows in src/backend/tests/data/ which don't require API keys.
"""

from __future__ import annotations

import contextlib
import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from lfx.graph.graph.base import Graph

from .test_execution_path_equivalence import ExecutionTrace, ExecutionTracer, assert_execution_equivalence

TEST_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

LOOP_CSV_FLOW = "loop_csv_test.json"
LOOP_CSV_NAME = "loop_test.csv"

# Test flows that should work without external dependencies
TEST_FLOWS = [
    "LoopTest.json",  # Simple loop with feedback
    LOOP_CSV_FLOW,  # Real-world failing case from issue
    "MemoryChatbotNoLLM.json",
]


@pytest.fixture
def stage_loop_csv() -> Generator[Callable[[dict, str], dict], None, None]:
    """Stage ``loop_test.csv`` in a graph scope's storage directory and point the flow at it.

    ``LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS`` defaults to true, so the File component may only
    read paths under ``config_dir/<user_id|flow_id>`` -- where an uploaded file actually lands.
    This fixture therefore stages the CSV the way an upload does (write it into the scope
    directory, hand the FileInput the ``"<scope>/<file name>"`` storage key that
    ``StorageService.resolve_component_path`` expands) instead of dropping it in the working
    directory, which is exactly the out-of-scope read the secure default denies.
    """
    staged: list[Path] = []

    def _stage(graph_data: dict, scope: str) -> dict:
        from lfx.services.deps import get_settings_service

        scope_dir = Path(get_settings_service().settings.config_dir) / scope
        scope_dir.mkdir(parents=True, exist_ok=True)
        target = scope_dir / LOOP_CSV_NAME
        shutil.copy(TEST_DATA_DIR / LOOP_CSV_NAME, target.as_posix())
        staged.append(target)

        storage_key = f"{scope}/{LOOP_CSV_NAME}"
        for node in graph_data.get("nodes", []):
            field = node.get("data", {}).get("node", {}).get("template", {}).get("path")
            if isinstance(field, dict) and field.get("file_path") == [LOOP_CSV_NAME]:
                field["file_path"] = [storage_key]
        return graph_data

    yield _stage

    for target in staged:
        if target.exists():
            target.unlink()
        with contextlib.suppress(OSError):
            target.parent.rmdir()


async def run_via_async_start_traced(graph: Graph) -> ExecutionTrace:
    """Run graph using async_start path with full tracing."""
    from lfx.graph.graph.constants import Finish

    trace = ExecutionTrace(path_name="async_start")
    tracer = ExecutionTracer(graph, trace)

    try:
        tracer.install()
        graph.prepare()

        results = []
        async for result in graph.async_start():
            if isinstance(result, Finish):
                break
            if hasattr(result, "vertex"):
                results.append(result)

        trace.final_outputs = results

    except Exception as e:
        trace.error = e
    finally:
        tracer.uninstall()

    return trace


async def run_via_arun_traced(graph: Graph) -> ExecutionTrace:
    """Run graph using arun path with full tracing."""
    from uuid import uuid4

    from langflow.schema.schema import INPUT_FIELD_NAME
    from lfx.schema.schema import InputValueRequest

    trace = ExecutionTrace(path_name="arun")
    tracer = ExecutionTracer(graph, trace)

    try:
        tracer.install()

        # Mimic run_graph_internal logic
        inputs = [InputValueRequest(components=[], input_value="", type="chat")]
        effective_session_id = str(uuid4())
        components = []
        inputs_list = []
        types = []

        for input_value_request in inputs:
            components.append(input_value_request.components or [])
            inputs_list.append({INPUT_FIELD_NAME: input_value_request.input_value or ""})
            types.append(input_value_request.type)

        graph.session_id = effective_session_id

        results = await graph.arun(
            inputs=inputs_list,
            inputs_components=components,
            types=types,
            outputs=[],  # Empty = run all vertices
            stream=False,
            session_id=effective_session_id,
            fallback_to_env_vars=False,
        )

        trace.final_outputs = results

    except Exception as e:
        trace.error = e
    finally:
        tracer.uninstall()

    return trace


@pytest.mark.parametrize("flow_name", TEST_FLOWS)
@pytest.mark.asyncio
@pytest.mark.usefixtures("client")
async def test_flow_execution_equivalence(flow_name: str, stage_loop_csv):
    """Test that a flow produces identical results via both execution paths."""
    from uuid import uuid4

    from lfx.graph.graph.base import Graph

    flow_path = TEST_DATA_DIR / flow_name

    if not flow_path.exists():
        pytest.skip(f"Flow not found: {flow_path}")

    # Load the flow
    with flow_path.open() as f:
        flow_data = json.load(f)

    graph_data = flow_data.get("data", flow_data)

    # Create two independent copies with valid UUIDs for persisted identifiers.
    user_id_async_start = str(uuid4())
    user_id_arun = str(uuid4())

    payload_async_start = deepcopy(graph_data)
    payload_arun = deepcopy(graph_data)

    if flow_name == LOOP_CSV_FLOW:
        # Each copy runs as its own user, so the CSV is staged once per storage scope.
        stage_loop_csv(payload_async_start, user_id_async_start)
        stage_loop_csv(payload_arun, user_id_arun)

    graph_for_async_start = Graph.from_payload(
        payload_async_start,
        flow_id=str(uuid4()),
        flow_name=flow_name,
        user_id=user_id_async_start,
    )

    graph_for_arun = Graph.from_payload(
        payload_arun,
        flow_id=str(uuid4()),
        flow_name=flow_name,
        user_id=user_id_arun,
    )

    # Run both paths with tracing
    trace_async_start = await run_via_async_start_traced(graph_for_async_start)
    trace_arun = await run_via_arun_traced(graph_for_arun)

    # Check for errors first
    if trace_async_start.error:
        pytest.fail(f"async_start path failed: {trace_async_start.error}")
    if trace_arun.error:
        pytest.fail(f"arun path failed: {trace_arun.error}")

    # Assert execution equivalence (same vertices, same counts)
    # Note: We only validate execution, not output format since:
    # - async_start yields VertexBuildResults incrementally
    # - arun returns grouped RunOutputs
    # The output structures are intentionally different
    try:
        assert_execution_equivalence(trace_async_start, trace_arun, allow_parallel_reordering=True)
    except AssertionError as e:
        # Provide detailed diagnostics
        msg = f"\n{'=' * 80}\nEXECUTION MISMATCH: {flow_name}\n{'=' * 80}\n"
        msg += f"\nAsync_start: {len(trace_async_start.vertices_executed)} vertices\n"
        msg += f"  {trace_async_start.execution_order}\n"
        msg += f"\nArun: {len(trace_arun.vertices_executed)} vertices\n"
        msg += f"  {trace_arun.execution_order}\n"
        only_async = set(trace_async_start.vertices_executed) - set(trace_arun.vertices_executed)
        only_arun = set(trace_arun.vertices_executed) - set(trace_async_start.vertices_executed)
        msg += f"\nOnly in async_start: {only_async}\n"
        msg += f"Only in arun: {only_arun}\n"

        # Show run_manager state differences
        if trace_async_start.run_manager_snapshots and trace_arun.run_manager_snapshots:
            async_snapshots = len(trace_async_start.run_manager_snapshots)
            arun_snapshots = len(trace_arun.run_manager_snapshots)
            msg += f"\nRun_manager snapshots: async={async_snapshots}, arun={arun_snapshots}\n"

        raise AssertionError(msg) from e


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
