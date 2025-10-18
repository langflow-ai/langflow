"""Demonstration of enhanced ExecutionTracer capabilities.

This test shows how to use state deltas and loop-specific tracking
to understand graph execution behavior.

Run with: pytest test_tracer_demo.py -v -s
"""

# ruff: noqa: T201

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_tracer_state_deltas_with_loop():
    """Demonstrate state delta tracking with a loop flow."""
    from lfx.graph.graph.base import Graph

    from .test_execution_path_equivalence import ExecutionTrace, ExecutionTracer

    # Load LoopTest.json
    test_data_dir = Path(__file__).resolve().parent.parent.parent / "data"
    loop_test_path = test_data_dir / "LoopTest.json"

    if not loop_test_path.exists():
        pytest.skip("LoopTest.json not found")

    with loop_test_path.open() as f:
        flow_data = json.load(f)

    graph_data = flow_data.get("data", flow_data)
    graph = Graph.from_payload(graph_data, flow_id="test-delta-demo", user_id="test-user")

    # Run with tracing
    trace = ExecutionTrace(path_name="demo")
    tracer = ExecutionTracer(graph, trace)

    try:
        tracer.install()
        graph.prepare()

        results = []
        async for result in graph.async_start():
            if hasattr(result, "vertex"):
                results.append(result)  # noqa: PERF401

    finally:
        tracer.uninstall()

    # ===== DEMONSTRATE STATE DELTAS =====
    print("\n" + "=" * 80)
    print("STATE DELTA DEMONSTRATION")
    print("=" * 80)

    print(trace.format_state_deltas())

    # Show specific deltas
    print("\nKey state changes:")
    for delta in trace.get_state_deltas():
        vertex_id = delta.get("vertex_id", "")

        # Highlight loop-related changes
        if "Loop" in vertex_id and "run_manager" in delta:
            rm_delta = delta["run_manager"]

            if "run_predecessors" in rm_delta:
                print(f"\n🔄 Loop {vertex_id} modified predecessors:")
                for vid, change in rm_delta["run_predecessors"].items():
                    if change["added"]:
                        print(f"   Added dependency: {vid} must wait for {change['added']}")

            if "run_map" in rm_delta:
                print(f"\n🔄 Loop {vertex_id} modified run_map:")
                for vid, change in rm_delta["run_map"].items():
                    if change["added"]:
                        print(f"   {vid} now has dependent: {change['added']}")

    # ===== DEMONSTRATE LOOP TRACKING =====
    print("\n" + "=" * 80)
    print("LOOP ITERATION TRACKING")
    print("=" * 80)

    print(trace.format_loop_iterations())

    # Show loop summary
    loop_summary = trace.get_loop_iterations_summary()
    for loop_id, summary in loop_summary.items():
        print(f"\n📊 Loop {loop_id} Summary:")
        print(f"   Total iterations: {summary['total_iterations']}")
        print(f"   Data length: {summary['data_length']}")
        print(f"   Max index reached: {summary['max_index_reached']}")

        # Check if loop iterated through all data
        if summary["max_index_reached"] >= summary["data_length"]:
            print("   ✅ Loop completed all iterations!")
        else:
            print(f"   ⚠️  Loop stopped early (reached {summary['max_index_reached']}/{summary['data_length']})")

    # Verify loop executed
    assert len(loop_summary) > 0, "Should have tracked at least one loop"


@pytest.mark.asyncio
async def test_compare_state_deltas_between_paths():
    """Compare state deltas between async_start and arun paths."""
    from copy import deepcopy

    from lfx.graph.graph.base import Graph

    from .test_execution_path_equivalence import ExecutionTrace, ExecutionTracer

    test_data_dir = Path(__file__).resolve().parent.parent.parent / "data"
    loop_test_path = test_data_dir / "LoopTest.json"

    if not loop_test_path.exists():
        pytest.skip("LoopTest.json not found")

    with loop_test_path.open() as f:
        flow_data = json.load(f)

    graph_data = flow_data.get("data", flow_data)

    # Run via async_start
    graph1 = Graph.from_payload(deepcopy(graph_data), flow_id="test-async", user_id="test-user")
    trace1 = ExecutionTrace(path_name="async_start")
    tracer1 = ExecutionTracer(graph1, trace1)

    try:
        tracer1.install()
        graph1.prepare()
        async for _result in graph1.async_start():
            pass
    finally:
        tracer1.uninstall()

    # Run via arun
    from uuid import uuid4

    from langflow.schema.schema import INPUT_FIELD_NAME
    from lfx.schema.schema import InputValueRequest

    graph2 = Graph.from_payload(deepcopy(graph_data), flow_id="test-arun", user_id="test-user")
    trace2 = ExecutionTrace(path_name="arun")
    tracer2 = ExecutionTracer(graph2, trace2)

    try:
        tracer2.install()

        inputs = [InputValueRequest(components=[], input_value="", type="chat")]
        session_id = str(uuid4())
        components = []
        inputs_list = []
        types = []

        for input_request in inputs:
            components.append(input_request.components or [])
            inputs_list.append({INPUT_FIELD_NAME: input_request.input_value or ""})
            types.append(input_request.type)

        graph2.session_id = session_id

        await graph2.arun(
            inputs=inputs_list,
            inputs_components=components,
            types=types,
            outputs=[],
            session_id=session_id,
            fallback_to_env_vars=False,
        )
    finally:
        tracer2.uninstall()

    # ===== COMPARE DELTAS =====
    print("\n" + "=" * 80)
    print("DELTA COMPARISON: async_start vs arun")
    print("=" * 80)

    deltas1 = trace1.get_state_deltas()
    deltas2 = trace2.get_state_deltas()

    print(f"\nAsync_start deltas: {len(deltas1)}")
    print(f"Arun deltas: {len(deltas2)}")

    # Find deltas that only appear in one path
    async_only_deltas = []
    for delta in deltas1:
        vid = delta.get("vertex_id")
        # Check if similar delta exists in trace2
        matching = [d for d in deltas2 if d.get("vertex_id") == vid]
        if not matching:
            async_only_deltas.append(delta)

    if async_only_deltas:
        print(f"\n⚠️  Found {len(async_only_deltas)} deltas only in async_start:")
        for delta in async_only_deltas[:5]:
            print(f"   {delta.get('vertex_id')}: {list(delta.keys())}")

    # Compare loop iterations
    loop1 = trace1.get_loop_iterations_summary()
    loop2 = trace2.get_loop_iterations_summary()

    print("\nLoop tracking:")
    print(f"  Async_start loops: {list(loop1.keys())}")
    print(f"  Arun loops: {list(loop2.keys())}")

    for loop_id in loop1:
        if loop_id in loop2:
            iter1 = loop1[loop_id]["total_iterations"]
            iter2 = loop2[loop_id]["total_iterations"]
            if iter1 == iter2:
                print(f"  ✅ {loop_id}: Both executed {iter1} times")
            else:
                print(f"  ⚠️  {loop_id}: async={iter1}, arun={iter2}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
