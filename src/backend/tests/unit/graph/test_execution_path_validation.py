"""Execution path validation using test data flows.

This test validates that both execution paths produce identical results
using the test flows in src/backend/tests/data/ which don't require API keys.
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

from .test_execution_path_equivalence import (
    ExecutionTrace,
    ExecutionTracer,
    assert_execution_equivalence,
)

TEST_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
STARTER_PROJECTS_DIR = Path(
    "/Users/ogabrielluiz/Projects/langflow/src/backend/base/langflow/initial_setup/starter_projects"
)

# Start with test data flows we know work
TEST_DATA_FLOWS = [
    ("data", "LoopTest.json"),  # Simple loop with feedback
    ("data", "loop_csv_test.json"),  # Real-world failing case from issue
    ("data", "MemoryChatbotNoLLM.json"),
]

# Add starter projects - start with simpler ones without API dependencies
STARTER_PROJECT_FLOWS = [
    ("starter", "Basic Prompting.json"),  # Will fail without API key - good to test error handling
    ("starter", "Text Sentiment Analysis.json"),
]

# Combine all test flows
TEST_FLOWS = TEST_DATA_FLOWS + STARTER_PROJECT_FLOWS


@pytest.fixture
def loop_csv_path() -> Generator[Path, None, None]:
    """Copy loop_test.csv to user's cache directory for File component access."""
    from platformdirs import user_cache_dir

    cache_dir = Path(user_cache_dir("langflow"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    file_path = cache_dir / "loop_test.csv"
    shutil.copy(TEST_DATA_DIR / "loop_test.csv", file_path)
    yield file_path
    # Cleanup - remove the file if it exists
    if file_path.exists():
        file_path.unlink()


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


@pytest.mark.parametrize("flow_info", TEST_FLOWS, ids=lambda x: x[1])
@pytest.mark.asyncio
@pytest.mark.usefixtures("loop_csv_path")
async def test_flow_execution_equivalence(flow_info: tuple[str, str]):
    """Test that a flow produces identical results via both execution paths."""
    from uuid import uuid4

    from lfx.graph.graph.base import Graph

    flow_type, flow_name = flow_info

    # Determine which directory to use
    if flow_type == "data":
        flow_path = TEST_DATA_DIR / flow_name
    elif flow_type == "starter":
        flow_path = STARTER_PROJECTS_DIR / flow_name
    else:
        pytest.skip(f"Unknown flow type: {flow_type}")

    if not flow_path.exists():
        pytest.skip(f"Flow not found: {flow_path}")

    # Load the flow
    flow_data = json.loads(flow_path.read_text())

    graph_data = flow_data.get("data", flow_data)

    # Create two independent copies - use valid UUIDs for flow_id
    graph_for_async_start = Graph.from_payload(
        deepcopy(graph_data),
        flow_id=str(uuid4()),
        flow_name=flow_name,
        user_id="test-user-async",
    )

    graph_for_arun = Graph.from_payload(
        deepcopy(graph_data),
        flow_id=str(uuid4()),
        flow_name=flow_name,
        user_id="test-user-arun",
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
