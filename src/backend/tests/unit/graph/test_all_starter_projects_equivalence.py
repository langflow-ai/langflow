"""Comprehensive test to validate execution path equivalence for all starter projects.

This test ensures that both execution paths produce identical results
for all starter projects in the codebase.
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from lfx.graph.graph.base import Graph

# Import the tracing infrastructure
from .test_execution_path_equivalence import (
    ExecutionTrace,
    ExecutionTracer,
    assert_execution_equivalence,
    assert_output_equivalence,
)

STARTER_PROJECTS_DIR = Path(
    "/Users/ogabrielluiz/Projects/langflow/src/backend/base/langflow/initial_setup/starter_projects"
)
TEST_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# Flows that require external dependencies or API keys
# Most starter projects use LLMs, so we'll test with simpler flows
# and mark these as xfail to track which ones work vs fail
SKIP_FLOWS = set()  # Start with none skipped, let them fail if they need deps


@pytest.fixture
def loop_csv_path() -> Generator[Path, None, None]:
    """Copy loop_test.csv to user's cache directory for File component access."""
    from platformdirs import user_cache_dir

    cache_dir = Path(user_cache_dir("langflow"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    file_path = cache_dir / "loop_test.csv"

    # Only copy if the source file exists
    source_file = TEST_DATA_DIR / "loop_test.csv"
    if source_file.exists():
        shutil.copy(source_file, file_path)

    yield file_path

    # Cleanup - remove the file if it exists
    if file_path.exists():
        file_path.unlink()


def get_all_starter_projects() -> list[Path]:
    """Get all starter project JSON files."""
    all_files = list(STARTER_PROJECTS_DIR.glob("*.json"))
    # Filter out skipped flows
    return [f for f in all_files if f.name not in SKIP_FLOWS]


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
    """Run graph using arun path with full tracing.

    This mimics how the /api/v1/run endpoint executes graphs.
    We use the same logic as run_graph_internal to ensure identical behavior.
    """
    from uuid import uuid4

    from langflow.schema.schema import INPUT_FIELD_NAME
    from lfx.schema.schema import InputValueRequest

    trace = ExecutionTrace(path_name="arun")
    tracer = ExecutionTracer(graph, trace)

    try:
        tracer.install()

        # Mimic run_graph_internal logic from process.py
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

        # Use empty outputs to run all vertices (same as debug mode)
        # This matches async_start behavior
        results = await graph.arun(
            inputs=inputs_list,
            inputs_components=components,
            types=types,
            outputs=[],  # Empty outputs = run all vertices
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


@pytest.mark.parametrize("flow_path", get_all_starter_projects(), ids=lambda p: p.name)
@pytest.mark.asyncio
@pytest.mark.usefixtures("loop_csv_path")
async def test_starter_project_equivalence(flow_path: Path):
    """Test that a starter project produces identical results via both execution paths."""
    from lfx.graph.graph.base import Graph

    # Load the flow
    with flow_path.open() as f:
        flow_data = json.load(f)

    graph_data = flow_data["data"]

    # Create two independent copies of the graph
    graph_for_async_start = Graph.from_payload(
        deepcopy(graph_data),
        flow_id=f"test-{flow_path.stem}-async",
        flow_name=flow_path.stem,
        user_id="test-user-async",  # Required for some components
    )

    graph_for_arun = Graph.from_payload(
        deepcopy(graph_data),
        flow_id=f"test-{flow_path.stem}-arun",
        flow_name=flow_path.stem,
        user_id="test-user-arun",  # Required for some components
    )

    # Run both paths with tracing
    trace_async_start = await run_via_async_start_traced(graph_for_async_start)
    trace_arun = await run_via_arun_traced(graph_for_arun)

    # Assert equivalence
    try:
        # First check if either path had errors
        if trace_async_start.error:
            pytest.fail(f"async_start path failed: {trace_async_start.error}")
        if trace_arun.error:
            pytest.fail(f"arun path failed: {trace_arun.error}")

        assert_execution_equivalence(trace_async_start, trace_arun, allow_parallel_reordering=True)
        assert_output_equivalence(trace_async_start, trace_arun)
    except AssertionError as e:
        # Provide detailed diagnostics on failure
        msg = f"\n{'=' * 80}\nEXECUTION PATH MISMATCH FOR: {flow_path.name}\n{'=' * 80}\n"
        msg += f"\n{e}\n"

        # Show errors if any
        if trace_async_start.error:
            msg += f"\nAsync_start error: {trace_async_start.error}\n"
        if trace_arun.error:
            msg += f"\nArun error: {trace_arun.error}\n"

        msg += "\nAsync_start execution order:\n"
        msg += f"  {trace_async_start.execution_order[:20]}...\n"
        msg += "\nArun execution order:\n"
        msg += f"  {trace_arun.execution_order[:20]}...\n"
        msg += f"\nAsync_start vertices: {set(trace_async_start.vertices_executed)}\n"
        msg += f"Arun vertices: {set(trace_arun.vertices_executed)}\n"

        # Show run_manager differences if available
        if trace_async_start.run_manager_snapshots and trace_arun.run_manager_snapshots:
            msg += f"\nAsync_start run_manager snapshots: {len(trace_async_start.run_manager_snapshots)}\n"
            msg += f"Arun run_manager snapshots: {len(trace_arun.run_manager_snapshots)}\n"

        raise AssertionError(msg) from e


@pytest.mark.asyncio
async def test_research_translation_loop():
    """Specific test for Research Translation Loop which has known loop behavior."""
    flow_path = STARTER_PROJECTS_DIR / "Research Translation Loop.json"

    if not flow_path.exists():
        pytest.skip(f"Flow not found: {flow_path}")

    from lfx.graph.graph.base import Graph

    with flow_path.open() as f:
        flow_data = json.load(f)

    graph_data = flow_data["data"]

    # Create two copies
    graph_async = Graph.from_payload(deepcopy(graph_data), flow_id="test-loop-async")
    graph_arun = Graph.from_payload(deepcopy(graph_data), flow_id="test-loop-arun")

    # Run both
    trace_async = await run_via_async_start_traced(graph_async)
    trace_arun = await run_via_arun_traced(graph_arun)

    # Both should succeed (after our fix)
    assert trace_async.error is None, f"async_start failed: {trace_async.error}"
    assert trace_arun.error is None, f"arun failed: {trace_arun.error}"

    # Both should execute the loop component
    async_loop_count = sum(1 for vid in trace_async.vertices_executed if "Loop" in vid)
    arun_loop_count = sum(1 for vid in trace_arun.vertices_executed if "Loop" in vid)

    assert async_loop_count > 0, "Loop component should execute in async_start"
    assert arun_loop_count > 0, "Loop component should execute in arun"

    # Both should execute the loop the same number of times
    assert async_loop_count == arun_loop_count, (
        f"Loop executed different number of times: async_start={async_loop_count}, arun={arun_loop_count}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-k", "not starter_project"])
