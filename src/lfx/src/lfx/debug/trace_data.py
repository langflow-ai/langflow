"""Core data structures for graph execution tracing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["ExecutionTrace", "ExecutionTracer"]


@dataclass
class ExecutionTrace:
    """Records the execution trace of a graph run."""

    path_name: str
    vertices_executed: list[str] = field(default_factory=list)
    execution_order: list[tuple[str, int]] = field(default_factory=list)
    final_outputs: list[Any] = field(default_factory=list)
    vertex_results: dict[str, Any] = field(default_factory=dict)
    context_snapshots: list[dict[str, Any]] = field(default_factory=list)
    run_manager_snapshots: list[dict[str, Any]] = field(default_factory=list)
    run_queue_snapshots: list[list[str]] = field(default_factory=list)
    error: Exception | None = None
    state_deltas: list[dict[str, Any]] = field(default_factory=list)
    loop_iterations: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def record_vertex_execution(self, vertex_id: str) -> None:
        """Record that a vertex was executed."""
        self.vertices_executed.append(vertex_id)
        run_count = self.vertices_executed.count(vertex_id)
        self.execution_order.append((vertex_id, run_count))

    def record_run_manager_snapshot(self, run_manager_state: dict[str, Any]) -> None:
        """Record a snapshot of the run_manager state."""
        self.run_manager_snapshots.append(run_manager_state.copy())

    def record_run_queue_snapshot(self, run_queue: list[str]) -> None:
        """Record a snapshot of the run queue."""
        self.run_queue_snapshots.append(run_queue.copy())

    def record_state_delta(self, vertex_id: str, delta: dict[str, Any]) -> None:
        """Record a state delta (what changed) for a vertex build."""
        delta["vertex_id"] = vertex_id
        delta["step"] = len(self.vertices_executed)
        self.state_deltas.append(delta)

    def record_loop_iteration(self, loop_id: str, iteration_data: dict[str, Any]) -> None:
        """Record a loop component iteration."""
        if loop_id not in self.loop_iterations:
            self.loop_iterations[loop_id] = []
        self.loop_iterations[loop_id].append(iteration_data)

    def get_vertex_run_count(self, vertex_id: str) -> int:
        """Get how many times a vertex was executed."""
        return self.vertices_executed.count(vertex_id)

    def get_state_deltas(self) -> list[dict[str, Any]]:
        """Get state deltas showing only what changed."""
        return self.state_deltas

    def get_loop_iterations_summary(self) -> dict[str, dict[str, Any]]:
        """Get summary of all loop iterations."""
        summary = {}
        for loop_id, iterations in self.loop_iterations.items():
            summary[loop_id] = {
                "total_iterations": len(iterations),
                "max_index_reached": max((it.get("index", 0) or 0 for it in iterations), default=0),
                "data_length": iterations[0].get("data_length", 0) if iterations else 0,
                "iterations": iterations,
            }
        return summary


class ExecutionTracer:
    """Traces graph execution to capture detailed runtime behavior."""

    def __init__(self, graph: Any, trace: ExecutionTrace) -> None:
        self.graph = graph
        self.trace = trace
        self.original_build_vertex = graph.build_vertex

    def _compute_run_manager_delta(self, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        """Compute what changed in run_manager state."""
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

        # Check queue changes
        before_to_run = set(before.get("vertices_to_run", set()))
        after_to_run = set(after.get("vertices_to_run", set()))
        if before_to_run != after_to_run:
            delta["vertices_to_run"] = {
                "added": list(after_to_run - before_to_run),
                "removed": list(before_to_run - after_to_run),
            }

        return delta

    def _compute_queue_delta(self, before: list[str], after: list[str]) -> dict[str, Any]:
        """Compute what changed in the queue."""
        before_set = set(before)
        after_set = set(after)

        return {
            "added": list(after_set - before_set),
            "removed": list(before_set - after_set),
            "before_size": len(before),
            "after_size": len(after),
        }

    def _capture_loop_state(self, vertex_id: str, vertex: Any) -> None:
        """Capture loop component state if this is a loop."""
        if not hasattr(vertex, "custom_component"):
            return

        component = vertex.custom_component
        if not hasattr(component, "__class__"):
            return

        class_name = component.__class__.__name__
        if "Loop" not in class_name:
            return

        # This is a loop! Capture its state
        loop_id = component._id if hasattr(component, "_id") else vertex_id  # noqa: SLF001

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

        if hasattr(self.graph, "get_run_queue"):
            before_queue = self.graph.get_run_queue()
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

        if hasattr(self.graph, "get_run_queue"):
            after_queue = self.graph.get_run_queue()
            self.trace.record_run_queue_snapshot(after_queue)

            if before_queue is not None:
                queue_delta = self._compute_queue_delta(before_queue, after_queue)
                # Always record queue delta, even if just size changed
                has_queue_changes = (
                    queue_delta["added"]
                    or queue_delta["removed"]
                    or queue_delta["before_size"] != queue_delta["after_size"]
                )
                if has_queue_changes:
                    delta["queue"] = queue_delta

        # Always record delta - even if no run_manager/queue changes,
        # we want to see that a vertex built without state changes
        self.trace.record_state_delta(vertex_id, delta)

        return result

    def install(self) -> None:
        """Install the tracer into the graph."""
        self.graph.build_vertex = self.traced_build_vertex

    def uninstall(self) -> None:
        """Restore the original build_vertex method."""
        self.graph.build_vertex = self.original_build_vertex
