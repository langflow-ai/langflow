"""Test suite for validating execution path equivalence between async_start and arun.

This module tests that both execution paths (async_start/astep and arun/process) produce
identical results, run the same components in compatible orders, and handle loops correctly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph
    from lfx.graph.schema import RunOutputs
    from lfx.schema.schema import InputValueRequest


@dataclass
class ExecutionTrace:
    """Records the execution trace of a graph run."""

    path_name: str
    vertices_executed: list[str] = field(default_factory=list)
    execution_order: list[tuple[str, int]] = field(default_factory=list)  # (vertex_id, run_count)
    final_outputs: list[RunOutputs] | None = None
    vertex_results: dict[str, Any] = field(default_factory=dict)
    context_snapshots: list[dict[str, Any]] = field(default_factory=list)
    run_manager_snapshots: list[dict[str, Any]] = field(default_factory=list)
    run_queue_snapshots: list[list[str]] = field(default_factory=list)
    error: Exception | None = None
    # New: State deltas and loop tracking
    state_deltas: list[dict[str, Any]] = field(default_factory=list)
    loop_iterations: dict[str, list[dict[str, Any]]] = field(default_factory=dict)  # loop_id -> iterations

    def record_vertex_execution(self, vertex_id: str) -> None:
        """Record that a vertex was executed."""
        self.vertices_executed.append(vertex_id)
        run_count = self.vertices_executed.count(vertex_id)
        self.execution_order.append((vertex_id, run_count))

    def record_context_snapshot(self, context: dict[str, Any]) -> None:
        """Record a snapshot of the graph context."""
        self.context_snapshots.append(context.copy())

    def record_run_manager_snapshot(self, run_manager_state: dict[str, Any]) -> None:
        """Record a snapshot of the run_manager state."""
        self.run_manager_snapshots.append(run_manager_state.copy())

    def record_run_queue_snapshot(self, run_queue: list[str]) -> None:
        """Record a snapshot of the run queue."""
        self.run_queue_snapshots.append(run_queue.copy())

    def record_state_delta(self, vertex_id: str, delta: dict[str, Any]) -> None:
        """Record a state delta (what changed) for a vertex build.

        Args:
            vertex_id: The vertex that was just built
            delta: Dictionary describing what changed
        """
        delta["vertex_id"] = vertex_id
        delta["step"] = len(self.vertices_executed)
        self.state_deltas.append(delta)

    def record_loop_iteration(self, loop_id: str, iteration_data: dict[str, Any]) -> None:
        """Record a loop component iteration.

        Args:
            loop_id: The loop component ID
            iteration_data: Data about this iteration (index, data, aggregated count, etc)
        """
        if loop_id not in self.loop_iterations:
            self.loop_iterations[loop_id] = []
        self.loop_iterations[loop_id].append(iteration_data)

    def get_vertex_run_count(self, vertex_id: str) -> int:
        """Get how many times a vertex was executed."""
        return self.vertices_executed.count(vertex_id)

    def get_run_manager_evolution(self) -> list[dict[str, Any]]:
        """Get the evolution of run_manager state over time.

        Returns:
            List of dicts showing how run_predecessors and run_map changed
        """
        evolution = []
        for i, snapshot in enumerate(self.run_manager_snapshots):
            evolution.append(
                {
                    "step": i,
                    "run_predecessors": snapshot.get("run_predecessors", {}),
                    "run_map": snapshot.get("run_map", {}),
                    "vertices_to_run": snapshot.get("vertices_to_run", set()),
                    "vertices_being_run": snapshot.get("vertices_being_run", set()),
                }
            )
        return evolution

    def get_queue_evolution(self) -> list[dict[str, Any]]:
        """Get the evolution of run_queue over time.

        Returns:
            List of dicts showing how the queue changed at each step
        """
        evolution = []
        for i, queue_snapshot in enumerate(self.run_queue_snapshots):
            vertex_id = self.vertices_executed[i // 2] if i // 2 < len(self.vertices_executed) else None
            evolution.append(
                {
                    "step": i,
                    "vertex_being_built": vertex_id,
                    "queue": queue_snapshot,
                    "queue_size": len(queue_snapshot),
                }
            )
        return evolution

    def get_state_deltas(self) -> list[dict[str, Any]]:
        """Get state deltas showing only what changed at each step.

        Returns:
            List of deltas with added/removed items
        """
        return self.state_deltas

    def get_loop_iterations_summary(self) -> dict[str, dict[str, Any]]:
        """Get summary of all loop iterations.

        Returns:
            Dictionary mapping loop_id to iteration summary
        """
        summary = {}
        for loop_id, iterations in self.loop_iterations.items():
            summary[loop_id] = {
                "total_iterations": len(iterations),
                "max_index_reached": max((it.get("index", 0) or 0 for it in iterations), default=0),
                "data_length": iterations[0].get("data_length", 0) if iterations else 0,
                "iterations": iterations,
            }
        return summary

    def format_state_deltas(self) -> str:
        """Format state deltas as human-readable text.

        Returns:
            Formatted string showing what changed at each step
        """
        lines = ["\n=== STATE DELTAS ===\n"]

        for delta in self.state_deltas:
            vertex_id = delta.get("vertex_id", "Unknown")
            step = delta.get("step", "?")

            lines.append(f"Step {step}: {vertex_id}")

            # Show run_manager changes
            if "run_manager" in delta:
                rm_delta = delta["run_manager"]

                if "run_predecessors" in rm_delta:
                    lines.append("  run_predecessors:")
                    for vid, change in rm_delta["run_predecessors"].items():
                        if change["added"]:
                            lines.append(f"    {vid} += {change['added']}")
                        if change["removed"]:
                            lines.append(f"    {vid} -= {change['removed']}")

                if "run_map" in rm_delta:
                    lines.append("  run_map:")
                    for vid, change in rm_delta["run_map"].items():
                        if change["added"]:
                            lines.append(f"    {vid} += {change['added']}")
                        if change["removed"]:
                            lines.append(f"    {vid} -= {change['removed']}")

            # Show queue changes
            if "queue" in delta:
                q_delta = delta["queue"]
                if q_delta["added"]:
                    lines.append(f"  queue += {q_delta['added']}")
                if q_delta["removed"]:
                    lines.append(f"  queue -= {q_delta['removed']}")
                lines.append(f"  queue size: {q_delta['before_size']} → {q_delta['after_size']}")

            lines.append("")

        return "\n".join(lines)

    def format_loop_iterations(self) -> str:
        """Format loop iterations as human-readable text.

        Returns:
            Formatted string showing loop progression
        """
        lines = ["\n=== LOOP ITERATIONS ===\n"]

        for loop_id, iterations in self.loop_iterations.items():
            lines.append(f"Loop: {loop_id}")
            lines.append(f"  Total iterations: {len(iterations)}")

            for i, iteration in enumerate(iterations):
                index = iteration.get("index", "?")
                data_len = iteration.get("data_length", "?")
                agg_count = iteration.get("aggregated_count", "?")
                lines.append(f"  Iteration {i}: index={index}/{data_len}, aggregated={agg_count}")

            lines.append("")

        return "\n".join(lines)


class ExecutionTracer:
    """Traces graph execution to capture detailed runtime behavior."""

    def __init__(self, graph: Graph, trace: ExecutionTrace) -> None:
        self.graph = graph
        self.trace = trace
        self.original_build_vertex = graph.build_vertex
        self._last_run_manager_state: dict[str, Any] | None = None
        self._last_queue_state: list[str] | None = None

    def _compute_run_manager_delta(self, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        """Compute what changed in run_manager state.

        Returns:
            Dictionary with only the changes
        """
        delta = {}

        # Check run_predecessors changes
        before_pred = before.get("run_predecessors", {})
        after_pred = after.get("run_predecessors", {})
        pred_changes = {}
        for vertex_id in set(list(before_pred.keys()) + list(after_pred.keys())):
            before_deps = set(before_pred.get(vertex_id, []))
            after_deps = set(after_pred.get(vertex_id, []))
            if before_deps != after_deps:
                pred_changes[vertex_id] = {
                    "added": list(after_deps - before_deps),
                    "removed": list(before_deps - after_deps),
                }
        if pred_changes:
            delta["run_predecessors"] = pred_changes

        # Check run_map changes
        before_map = before.get("run_map", {})
        after_map = after.get("run_map", {})
        map_changes = {}
        for vertex_id in set(list(before_map.keys()) + list(after_map.keys())):
            before_deps = set(before_map.get(vertex_id, []))
            after_deps = set(after_map.get(vertex_id, []))
            if before_deps != after_deps:
                map_changes[vertex_id] = {
                    "added": list(after_deps - before_deps),
                    "removed": list(before_deps - after_deps),
                }
        if map_changes:
            delta["run_map"] = map_changes

        # Check vertices_to_run changes
        before_to_run = set(before.get("vertices_to_run", set()))
        after_to_run = set(after.get("vertices_to_run", set()))
        if before_to_run != after_to_run:
            delta["vertices_to_run"] = {
                "added": list(after_to_run - before_to_run),
                "removed": list(before_to_run - after_to_run),
            }

        # Check vertices_being_run changes
        before_being_run = set(before.get("vertices_being_run", set()))
        after_being_run = set(after.get("vertices_being_run", set()))
        if before_being_run != after_being_run:
            delta["vertices_being_run"] = {
                "added": list(after_being_run - before_being_run),
                "removed": list(before_being_run - after_being_run),
            }

        return delta

    def _compute_queue_delta(self, before: list[str], after: list[str]) -> dict[str, Any]:
        """Compute what changed in the queue.

        Returns:
            Dictionary with queue changes
        """
        before_set = set(before)
        after_set = set(after)

        return {
            "added": list(after_set - before_set),
            "removed": list(before_set - after_set),
            "before_size": len(before),
            "after_size": len(after),
        }

    def _capture_loop_state(self, vertex_id: str, vertex: Any) -> None:
        """Capture loop component state if this is a loop.

        Args:
            vertex_id: The vertex ID
            vertex: The vertex object
        """
        # Check if this is a loop component
        if not hasattr(vertex, "custom_component"):
            return

        component = vertex.custom_component
        if not hasattr(component, "__class__"):
            return

        class_name = component.__class__.__name__
        if "Loop" not in class_name:
            return

        # This is a loop! Capture its state
        loop_id = component._id if hasattr(component, "_id") else vertex_id

        iteration_data = {
            "step": len(self.trace.vertices_executed),
            "vertex_id": vertex_id,
        }

        # Capture loop context state
        if hasattr(component, "ctx"):
            iteration_data["index"] = component.ctx.get(f"{loop_id}_index", None)
            iteration_data["data_length"] = len(component.ctx.get(f"{loop_id}_data", []))
            iteration_data["aggregated_count"] = len(component.ctx.get(f"{loop_id}_aggregated", []))
            iteration_data["initialized"] = component.ctx.get(f"{loop_id}_initialized", False)

        self.trace.record_loop_iteration(loop_id, iteration_data)

    async def traced_build_vertex(self, vertex_id: str, *args, **kwargs):
        """Wrapped build_vertex that records execution."""
        self.trace.record_vertex_execution(vertex_id)

        # Capture state BEFORE building
        before_run_manager = None
        before_queue = None

        if hasattr(self.graph, "run_manager"):
            before_run_manager = self.graph.run_manager.to_dict()
            self.trace.record_run_manager_snapshot(before_run_manager)

        if hasattr(self.graph, "_run_queue"):
            before_queue = list(self.graph._run_queue)
            self.trace.record_run_queue_snapshot(before_queue)

        # Call original method
        result = await self.original_build_vertex(vertex_id, *args, **kwargs)

        # Record vertex result
        if result and hasattr(result, "result"):
            self.trace.vertex_results[vertex_id] = result.result

        # Capture loop state if this is a loop
        if result and hasattr(result, "vertex"):
            self._capture_loop_state(vertex_id, result.vertex)

        # Capture state AFTER building and compute deltas
        delta = {"vertex_id": vertex_id}

        if hasattr(self.graph, "run_manager"):
            after_run_manager = self.graph.run_manager.to_dict()
            self.trace.record_run_manager_snapshot(after_run_manager)

            if before_run_manager:
                run_manager_delta = self._compute_run_manager_delta(before_run_manager, after_run_manager)
                if run_manager_delta:
                    delta["run_manager"] = run_manager_delta

        if hasattr(self.graph, "_run_queue"):
            after_queue = list(self.graph._run_queue)
            self.trace.record_run_queue_snapshot(after_queue)

            if before_queue is not None:
                queue_delta = self._compute_queue_delta(before_queue, after_queue)
                if queue_delta["added"] or queue_delta["removed"]:
                    delta["queue"] = queue_delta

        # Record delta if anything changed
        if len(delta) > 2:  # More than just vertex_id and step
            self.trace.record_state_delta(vertex_id, delta)

        return result

    def install(self) -> None:
        """Install the tracer into the graph."""
        self.graph.build_vertex = self.traced_build_vertex

    def uninstall(self) -> None:
        """Restore the original build_vertex method."""
        self.graph.build_vertex = self.original_build_vertex


async def run_via_async_start(
    graph: Graph,
    inputs: list[InputValueRequest] | None = None,
    _outputs: list[str] | None = None,
) -> ExecutionTrace:
    """Run graph using async_start path and capture trace.

    This mimics how the CLI `lfx run` command executes graphs.
    """
    trace = ExecutionTrace(path_name="async_start")
    tracer = ExecutionTracer(graph, trace)

    try:
        tracer.install()
        graph.prepare()

        results = []
        input_dict = None
        if inputs:
            input_dict = inputs[0]

        async for result in graph.async_start(inputs=input_dict):
            if hasattr(result, "vertex"):
                results.append(result)  # noqa: PERF401

        trace.final_outputs = results

    except Exception as e:
        trace.error = e
    finally:
        tracer.uninstall()

    return trace


async def run_via_arun(
    graph: Graph,
    inputs: list[InputValueRequest] | None = None,
    outputs: list[str] | None = None,
) -> ExecutionTrace:
    """Run graph using arun path and capture trace.

    This mimics how the /api/v1/run endpoint executes graphs.
    """
    trace = ExecutionTrace(path_name="arun")
    tracer = ExecutionTracer(graph, trace)

    try:
        tracer.install()
        graph.prepare()

        # Convert inputs to the format expected by arun
        inputs_list = []
        inputs_components = []
        types = []

        if inputs:
            for input_request in inputs:
                inputs_list.append({"message": input_request.input_value})
                inputs_components.append(input_request.components or [])
                types.append(input_request.type or "chat")

        results = await graph.arun(
            inputs=inputs_list,
            inputs_components=inputs_components,
            types=types,
            outputs=outputs or [],
            session_id=graph.session_id or "test-session",
        )

        trace.final_outputs = results

    except Exception as e:
        trace.error = e
    finally:
        tracer.uninstall()

    return trace


def assert_execution_equivalence(
    trace1: ExecutionTrace,
    trace2: ExecutionTrace,
    *,
    allow_parallel_reordering: bool = True,
) -> None:
    """Assert that two execution traces are equivalent.

    Args:
        trace1: First execution trace
        trace2: Second execution trace
        allow_parallel_reordering: If True, allows vertices in the same layer
                                  to execute in different orders (since they run
                                  in parallel in the arun path)
    """
    # Both should succeed or both should fail
    if trace1.error or trace2.error:
        assert (trace1.error is None) == (trace2.error is None), (
            f"{trace1.path_name} error: {trace1.error}, {trace2.path_name} error: {trace2.error}"
        )

    # Should execute the same set of vertices
    vertices1 = set(trace1.vertices_executed)
    vertices2 = set(trace2.vertices_executed)

    assert vertices1 == vertices2, (
        f"Different vertices executed:\n"
        f"{trace1.path_name}: {vertices1}\n"
        f"{trace2.path_name}: {vertices2}\n"
        f"Only in {trace1.path_name}: {vertices1 - vertices2}\n"
        f"Only in {trace2.path_name}: {vertices2 - vertices1}"
    )

    # Should execute each vertex the same number of times
    for vertex_id in vertices1:
        count1 = trace1.get_vertex_run_count(vertex_id)
        count2 = trace2.get_vertex_run_count(vertex_id)

        assert count1 == count2, (
            f"Vertex {vertex_id} executed different number of times:\n"
            f"{trace1.path_name}: {count1} times\n"
            f"{trace2.path_name}: {count2} times"
        )

    # If not allowing reordering, execution order should be identical
    if not allow_parallel_reordering:
        assert trace1.execution_order == trace2.execution_order, (
            f"Execution order differs:\n"
            f"{trace1.path_name}: {trace1.execution_order}\n"
            f"{trace2.path_name}: {trace2.execution_order}"
        )


def compare_run_manager_evolution(trace1: ExecutionTrace, trace2: ExecutionTrace) -> dict[str, Any]:
    """Compare how run_manager state evolved in both traces.

    Returns:
        Dictionary with comparison results highlighting differences
    """
    evo1 = trace1.get_run_manager_evolution()
    evo2 = trace2.get_run_manager_evolution()

    differences = []

    max_steps = max(len(evo1), len(evo2))
    for step in range(max_steps):
        step_diff = {"step": step}

        if step < len(evo1) and step < len(evo2):
            # Compare run_predecessors
            pred1 = evo1[step]["run_predecessors"]
            pred2 = evo2[step]["run_predecessors"]
            if pred1 != pred2:
                step_diff["run_predecessors_diff"] = {
                    "trace1": pred1,
                    "trace2": pred2,
                }

            # Compare run_map
            map1 = evo1[step]["run_map"]
            map2 = evo2[step]["run_map"]
            if map1 != map2:
                step_diff["run_map_diff"] = {
                    "trace1": map1,
                    "trace2": map2,
                }

            if len(step_diff) > 1:  # Has differences beyond 'step'
                differences.append(step_diff)

    return {
        "has_differences": len(differences) > 0,
        "differences": differences,
        "trace1_steps": len(evo1),
        "trace2_steps": len(evo2),
    }


def format_execution_comparison(trace1: ExecutionTrace, trace2: ExecutionTrace) -> str:
    """Format a detailed comparison of two execution traces for debugging.

    Returns:
        Human-readable string showing execution differences
    """
    lines = []
    lines.append(f"\n{'=' * 80}")
    lines.append(f"EXECUTION COMPARISON: {trace1.path_name} vs {trace2.path_name}")
    lines.append(f"{'=' * 80}\n")

    # Execution order comparison
    lines.append("Execution Order:")
    lines.append(f"  {trace1.path_name}: {trace1.execution_order[:10]}...")
    lines.append(f"  {trace2.path_name}: {trace2.execution_order[:10]}...\n")

    # Vertex count comparison
    for vid in set(trace1.vertices_executed + trace2.vertices_executed):
        count1 = trace1.get_vertex_run_count(vid)
        count2 = trace2.get_vertex_run_count(vid)
        if count1 != count2:
            lines.append(f"  {vid}: {trace1.path_name}={count1}, {trace2.path_name}={count2}")

    # Run manager differences
    rm_comparison = compare_run_manager_evolution(trace1, trace2)
    if rm_comparison["has_differences"]:
        lines.append(f"\nRun Manager Differences Found: {len(rm_comparison['differences'])} steps")
        lines.extend(f"  Step {diff['step']}: {list(diff.keys())}" for diff in rm_comparison["differences"][:5])

    # Queue evolution
    lines.append("\nQueue Snapshots:")
    lines.append(f"  {trace1.path_name}: {len(trace1.run_queue_snapshots)} snapshots")
    lines.append(f"  {trace2.path_name}: {len(trace2.run_queue_snapshots)} snapshots")

    return "\n".join(lines)


def assert_output_equivalence(trace1: ExecutionTrace, trace2: ExecutionTrace) -> None:
    """Assert that two execution traces produced equivalent outputs."""
    # Compare final outputs
    if trace1.final_outputs and trace2.final_outputs:
        # Both should have outputs
        assert len(trace1.final_outputs) == len(trace2.final_outputs), (
            f"Different number of outputs:\n"
            f"{trace1.path_name}: {len(trace1.final_outputs)}\n"
            f"{trace2.path_name}: {len(trace2.final_outputs)}"
        )

        # Compare output results (Note: exact comparison may need to be relaxed
        # depending on non-deterministic components like LLMs)
        for i, (out1, out2) in enumerate(zip(trace1.final_outputs, trace2.final_outputs, strict=True)):
            # Basic structural comparison
            if hasattr(out1, "outputs") and hasattr(out2, "outputs"):
                assert len(out1.outputs) == len(out2.outputs), (
                    f"Output {i} has different number of results:\n"
                    f"{trace1.path_name}: {len(out1.outputs)}\n"
                    f"{trace2.path_name}: {len(out2.outputs)}"
                )


@pytest.mark.asyncio
async def test_simple_graph_equivalence():
    """Test that a simple graph executes identically via both paths."""
    # TODO: Create a simple graph with 3-4 components (no loops)
    # and verify both paths produce identical results
    pytest.skip("Awaiting simple test graph implementation")


@pytest.mark.asyncio
async def test_loop_graph_equivalence():
    """Test that a graph with LoopComponent executes identically via both paths.

    This is the critical test for the loop context isolation issue.
    """
    # TODO: Create a graph with LoopComponent and verify both paths
    # execute the loop the same number of times and produce identical results
    pytest.skip("Awaiting loop test graph implementation")


@pytest.mark.asyncio
async def test_loop_context_isolation():
    """Test that loop context is properly isolated between iterations.

    This test specifically checks that the loop's internal state
    (index, aggregated results) resets correctly for each new input.
    """
    # TODO: Run a loop graph multiple times with different inputs
    # and verify that context state doesn't leak between runs
    pytest.skip("Awaiting context isolation test implementation")


@pytest.mark.asyncio
async def test_execution_trace_capture():
    """Test that ExecutionTracer correctly captures execution details."""
    # TODO: Verify the tracing infrastructure works correctly
    pytest.skip("Awaiting trace infrastructure test")
