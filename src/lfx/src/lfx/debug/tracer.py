"""Interactive graph execution tracer for debugging in Jupyter notebooks.

Usage:
    from lfx.debug.tracer import trace_graph, compare_paths

    # Load and trace a flow
    trace = await trace_graph("path/to/flow.json", method="async_start")

    # View results
    trace.show()              # Rich visual report
    trace.show_deltas()       # State changes only
    trace.show_loops()        # Loop progression
    trace.export_html()       # Save HTML report

    # Compare execution paths
    comparison = await compare_paths("path/to/flow.json")
    comparison.show()         # Show differences
"""

# ruff: noqa: T201

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GraphTrace:
    """Results from tracing a graph execution."""

    flow_name: str
    execution_method: str  # "async_start" or "arun"
    vertices_executed: list[str] = field(default_factory=list)
    execution_order: list[tuple[str, int]] = field(default_factory=list)
    state_deltas: list[dict[str, Any]] = field(default_factory=list)
    loop_iterations: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    error: Exception | None = None

    def show(self) -> None:
        """Display rich visual report of execution."""
        print(f"\n{'=' * 80}")
        print(f"Graph Execution Report: {self.flow_name}")
        print(f"Method: {self.execution_method}")
        print(f"{'=' * 80}\n")

        if self.error:
            print(f"❌ Error: {self.error}\n")
            return

        # Execution summary
        print(f"Components executed: {len(set(self.vertices_executed))}")
        print(f"Total executions: {len(self.vertices_executed)}")
        print(f"State changes: {len(self.state_deltas)}")
        print(f"Loops detected: {len(self.loop_iterations)}\n")

        # Execution order
        print("Execution Order:")
        max_display = 20
        for step, (vertex_id, count) in enumerate(self.execution_order[:max_display], 1):
            short_id = vertex_id.split("-")[0] if "-" in vertex_id else vertex_id
            print(f"  {step}. {short_id} (run #{count})")
        if len(self.execution_order) > max_display:
            print(f"  ... and {len(self.execution_order) - max_display} more")

        print()

    def show_deltas(self, *, verbose: bool = True) -> None:
        """Display state changes.

        Args:
            verbose: If True, show all components. If False, only show components with changes.
        """
        print(f"\n{'=' * 80}")
        print("State Changes")
        print(f"{'=' * 80}\n")

        for delta in self.state_deltas:
            vertex_id = delta.get("vertex_id", "Unknown")
            short_id = vertex_id.split("-")[0] if "-" in vertex_id else vertex_id

            # Check if this delta has meaningful changes
            has_changes = "run_manager" in delta or "queue" in delta

            # Skip if not verbose and no changes
            if not verbose and not has_changes:
                continue

            print(f"📍 {short_id}:")

            if not has_changes:
                print("   (no state changes)")
            else:
                if "run_manager" in delta:
                    rm = delta["run_manager"]
                    if "run_predecessors" in rm:
                        for vid, change in rm["run_predecessors"].items():
                            short_vid = vid.split("-")[0] if "-" in vid else vid
                            if change["added"]:
                                added = [v.split("-")[0] for v in change["added"]]
                                print(f"   run_predecessors[{short_vid}] += {added}")
                            if change["removed"]:
                                removed = [v.split("-")[0] for v in change["removed"]]
                                print(f"   run_predecessors[{short_vid}] -= {removed}")

                    if "run_map" in rm:
                        for vid, change in rm["run_map"].items():
                            short_vid = vid.split("-")[0] if "-" in vid else vid
                            if change["added"]:
                                added = [v.split("-")[0] for v in change["added"]]
                                print(f"   run_map[{short_vid}] += {added}")
                            if change["removed"]:
                                removed = [v.split("-")[0] for v in change["removed"]]
                                print(f"   run_map[{short_vid}] -= {removed}")

                if "queue" in delta:
                    q = delta["queue"]
                    if q["added"]:
                        added = [v.split("-")[0] for v in q["added"]]
                        print(f"   queue += {added}")
                    if q["removed"]:
                        removed = [v.split("-")[0] for v in q["removed"]]
                        print(f"   queue -= {removed}")
                    print(f"   queue size: {q['before_size']} → {q['after_size']}")

            print()

    def show_loops(self) -> None:
        """Display loop progression."""
        print(f"\n{'=' * 80}")
        print("Loop Iterations")
        print(f"{'=' * 80}\n")

        if not self.loop_iterations:
            print("No loops detected")
            return

        for loop_id, iterations in self.loop_iterations.items():
            short_id = loop_id.split("-")[0] if "-" in loop_id else loop_id
            print(f"🔄 {short_id}:")
            print(f"   Total iterations: {len(iterations)}")

            if iterations:
                first = iterations[0]
                data_len = first.get("data_length", 0)
                print(f"   Data to process: {data_len} items")

                # Show progression
                max_loop_display = 10
                for i, it in enumerate(iterations[:max_loop_display]):
                    idx = it.get("index", "?")
                    agg = it.get("aggregated_count", "?")
                    print(f"   [{i}] index={idx}, aggregated={agg}")

                if len(iterations) > max_loop_display:
                    print(f"   ... and {len(iterations) - max_loop_display} more iterations")

                # Check completion
                last = iterations[-1]
                final_idx = last.get("index", 0) or 0
                if final_idx >= data_len:
                    print(f"   ✅ Completed all {data_len} items")
                else:
                    print(f"   ⚠️  Stopped at {final_idx}/{data_len}")

            print()


async def trace_graph(
    flow_path: str | Path,
    method: str = "both",
    *,
    inputs: Any = None,  # noqa: ARG001
    show: bool = True,
) -> GraphTrace | dict[str, GraphTrace]:
    """Trace a graph execution for debugging.

    Args:
        flow_path: Path to flow JSON file
        method: "async_start", "arun", or "both"
        inputs: Optional inputs to pass
        show: Whether to automatically display results

    Returns:
        GraphTrace if single method, dict of traces if "both"

    Example:
        # In Jupyter notebook:
        trace = await trace_graph("my_flow.json", method="async_start")
        trace.show()
        trace.show_deltas()
        trace.show_loops()
    """
    # Load flow
    flow_path = Path(flow_path)
    flow_data = json.loads(flow_path.read_text())
    graph_data = flow_data.get("data", flow_data)

    if method == "both":
        async_trace = await _trace_async_start(graph_data, flow_path.stem)
        arun_trace = await _trace_arun(graph_data, flow_path.stem)

        if show:
            print(f"\n{'=' * 80}")
            print("ASYNC_START PATH")
            async_trace.show()

            print(f"\n{'=' * 80}")
            print("ARUN PATH")
            arun_trace.show()

        return {"async_start": async_trace, "arun": arun_trace}

    if method == "async_start":
        trace = await _trace_async_start(graph_data, flow_path.stem)
        if show:
            trace.show()
        return trace

    if method == "arun":
        trace = await _trace_arun(graph_data, flow_path.stem)
        if show:
            trace.show()
        return trace

    msg = f"Invalid method: {method}. Use 'async_start', 'arun', or 'both'"
    raise ValueError(msg)


async def _trace_async_start(graph_data: dict, flow_name: str) -> GraphTrace:
    """Trace via async_start path."""
    from lfx.graph.graph.base import Graph
    from lfx.graph.graph.constants import Finish

    from .trace_data import ExecutionTrace, ExecutionTracer

    graph = Graph.from_payload(graph_data)

    trace = ExecutionTrace(path_name="async_start")
    tracer = ExecutionTracer(graph, trace)

    try:
        tracer.install()
        graph.prepare()

        async for result in graph.async_start():
            if isinstance(result, Finish):
                break

    except Exception as e:  # noqa: BLE001
        trace.error = e
    finally:
        tracer.uninstall()

    # Convert to GraphTrace
    return GraphTrace(
        flow_name=flow_name,
        execution_method="async_start",
        vertices_executed=trace.vertices_executed,
        execution_order=trace.execution_order,
        state_deltas=trace.state_deltas,
        loop_iterations=trace.loop_iterations,
        error=trace.error,
    )


async def _trace_arun(graph_data: dict, flow_name: str) -> GraphTrace:
    """Trace via arun path."""
    from uuid import uuid4

    from lfx.graph.graph.base import Graph
    from lfx.schema.schema import InputValueRequest

    from langflow.schema.schema import INPUT_FIELD_NAME

    from .trace_data import ExecutionTrace, ExecutionTracer

    graph = Graph.from_payload(graph_data)

    trace = ExecutionTrace(path_name="arun")
    tracer = ExecutionTracer(graph, trace)

    try:
        tracer.install()

        inputs = [InputValueRequest(components=[], input_value="", type="chat")]
        session_id = str(uuid4())
        components = []
        inputs_list = []
        types = []

        for input_request in inputs:
            components.append(input_request.components or [])
            inputs_list.append({INPUT_FIELD_NAME: input_request.input_value or ""})
            types.append(input_request.type)

        graph.session_id = session_id

        await graph.arun(
            inputs=inputs_list,
            inputs_components=components,
            types=types,
            outputs=[],
            session_id=session_id,
            fallback_to_env_vars=False,
        )

    except Exception as e:  # noqa: BLE001
        trace.error = e
    finally:
        tracer.uninstall()

    return GraphTrace(
        flow_name=flow_name,
        execution_method="arun",
        vertices_executed=trace.vertices_executed,
        execution_order=trace.execution_order,
        state_deltas=trace.state_deltas,
        loop_iterations=trace.loop_iterations,
        error=trace.error,
    )


async def compare_paths(flow_path: str | Path) -> dict[str, Any]:
    """Compare both execution paths and show differences.

    Args:
        flow_path: Path to flow JSON

    Returns:
        Dict with comparison results

    Example:
        comparison = await compare_paths("my_flow.json")
        # Automatically shows differences
    """
    traces = await trace_graph(flow_path, method="both", show=False)

    async_trace = traces["async_start"]
    arun_trace = traces["arun"]

    # Compare
    comparison = {
        "async_start": {
            "components": len(set(async_trace.vertices_executed)),
            "total_executions": len(async_trace.vertices_executed),
            "loops": len(async_trace.loop_iterations),
            "error": async_trace.error,
        },
        "arun": {
            "components": len(set(arun_trace.vertices_executed)),
            "total_executions": len(arun_trace.vertices_executed),
            "loops": len(arun_trace.loop_iterations),
            "error": arun_trace.error,
        },
    }

    # Show comparison
    print(f"\n{'=' * 80}")
    print("Execution Path Comparison")
    print(f"{'=' * 80}\n")

    print("Async_start:")
    print(f"  Components: {comparison['async_start']['components']}")
    print(f"  Executions: {comparison['async_start']['total_executions']}")
    print(f"  Loops: {comparison['async_start']['loops']}")
    if comparison["async_start"]["error"]:
        print(f"  ❌ Error: {comparison['async_start']['error']}")

    print("\nArun:")
    print(f"  Components: {comparison['arun']['components']}")
    print(f"  Executions: {comparison['arun']['total_executions']}")
    print(f"  Loops: {comparison['arun']['loops']}")
    if comparison["arun"]["error"]:
        print(f"  ❌ Error: {comparison['arun']['error']}")

    # Check for differences
    if comparison["async_start"] == comparison["arun"]:
        print("\n✅ Both paths executed identically!")
    else:
        print("\n⚠️  Paths differ:")
        if comparison["async_start"]["components"] != comparison["arun"]["components"]:
            print(f"   Components: {comparison['async_start']['components']} vs {comparison['arun']['components']}")
        if comparison["async_start"]["total_executions"] != comparison["arun"]["total_executions"]:
            async_count = comparison["async_start"]["total_executions"]
            arun_count = comparison["arun"]["total_executions"]
            print(f"   Executions: {async_count} vs {arun_count}")

    return comparison
