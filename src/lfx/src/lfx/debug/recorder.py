"""Graph execution recorder with time-travel debugging.

Record a graph execution once, then jump to any point to inspect state.

Usage:
    from lfx.debug.recorder import record_graph

    # Record phase
    recording = await record_graph("flow.json")

    # View timeline
    recording.show_timeline()

    # Jump to any component
    recording.jump_to("LoopComponent")

    # See state at that point
    recording.show_state()

    # Replay from here
    results = await recording.replay_from_here()
"""

# ruff: noqa: T201

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ComponentSnapshot:
    """Snapshot of a component's execution."""

    vertex_id: str
    step: int  # Execution step number
    inputs: dict[str, Any]  # Component inputs
    outputs: Any  # Component outputs/result
    graph_state_before: dict[str, Any]  # State before component executed
    graph_state_after: dict[str, Any]  # State after component executed
    queue_state_before: list[str]  # Queue before
    queue_state_after: list[str]  # Queue after
    context: dict[str, Any]  # Graph context
    error: str | None = None  # Error message (string for pickle compatibility)

    def get_delta(self) -> dict[str, Any]:
        """Compute what changed during this component's execution.

        Returns:
            Dictionary with queue changes, run_manager changes, etc.
        """
        delta = {}

        # Queue changes
        queue_before = set(self.queue_state_before)
        queue_after = set(self.queue_state_after)
        added = queue_after - queue_before
        removed = queue_before - queue_after

        if added or removed:
            delta["queue"] = {
                "added": list(added),
                "removed": list(removed),
            }

        # run_predecessors changes
        pred_before = self.graph_state_before.get("run_predecessors", {})
        pred_after = self.graph_state_after.get("run_predecessors", {})

        pred_changes = {}
        for k in set(list(pred_before.keys()) + list(pred_after.keys())):
            before = set(pred_before.get(k, []))
            after = set(pred_after.get(k, []))
            if before != after:
                pred_changes[k] = {
                    "added": list(after - before),
                    "removed": list(before - after),
                }

        if pred_changes:
            delta["run_predecessors"] = pred_changes

        # run_map changes
        map_before = self.graph_state_before.get("run_map", {})
        map_after = self.graph_state_after.get("run_map", {})

        map_changes = {}
        for k in set(list(map_before.keys()) + list(map_after.keys())):
            before = set(map_before.get(k, []))
            after = set(map_after.get(k, []))
            if before != after:
                map_changes[k] = {
                    "added": list(after - before),
                    "removed": list(before - after),
                }

        if map_changes:
            delta["run_map"] = map_changes

        return delta


@dataclass
class GraphRecording:
    """Recording of a complete graph execution with VCR capabilities."""

    flow_name: str
    execution_method: str
    snapshots: list[ComponentSnapshot] = field(default_factory=list)
    current_position: int = 0
    flow_data: dict[str, Any] | None = None  # Store original flow for replay

    def save(self, file_path: str | Path) -> None:
        """Save recording to file for later replay.

        Args:
            file_path: Path to save the recording
        """
        with Path(file_path).open("wb") as f:
            pickle.dump(self, f)
        print(f"✅ Saved recording to {file_path}")

    @classmethod
    def load(cls, file_path: str | Path) -> GraphRecording:
        """Load a saved recording.

        Args:
            file_path: Path to the saved recording

        Returns:
            GraphRecording instance
        """
        with Path(file_path).open("rb") as f:
            recording = pickle.load(f)  # noqa: S301
        print(f"✅ Loaded recording from {file_path}")
        return recording

    def show_timeline(self) -> None:
        """Display the execution timeline."""
        print(f"\n{'=' * 80}")
        print(f"Execution Timeline: {self.flow_name}")
        print(f"Method: {self.execution_method}")
        print(f"{'=' * 80}\n")

        print(f"Total components: {len(self.snapshots)}")
        print(f"Current position: {self.current_position}\n")

        print("Timeline:")
        for i, snapshot in enumerate(self.snapshots):
            short_id = snapshot.vertex_id.split("-")[0] if "-" in snapshot.vertex_id else snapshot.vertex_id

            # Mark current position
            marker = "👉 " if i == self.current_position else "   "

            # Show if had error
            status = "❌" if snapshot.error else "✅"

            print(f"{marker}[{i:3d}] {status} {short_id}")

        print()

    def jump_to(self, component_name_or_step: str | int) -> None:
        """Jump to a specific component or step.

        Args:
            component_name_or_step: Component name (e.g., "LoopComponent") or step number
        """
        if isinstance(component_name_or_step, int):
            if 0 <= component_name_or_step < len(self.snapshots):
                self.current_position = component_name_or_step
                print(f"✅ Jumped to step {component_name_or_step}")
            else:
                print(f"❌ Invalid step: {component_name_or_step} (max: {len(self.snapshots) - 1})")
            return

        # Search by component name
        for i, snapshot in enumerate(self.snapshots):
            if component_name_or_step in snapshot.vertex_id:
                self.current_position = i
                short_id = snapshot.vertex_id.split("-")[0]
                print(f"✅ Jumped to step {i}: {short_id}")
                return

        print(f"❌ Component '{component_name_or_step}' not found")

    def show_state(self) -> None:
        """Show graph state at current position."""
        if self.current_position >= len(self.snapshots):
            print("❌ Invalid position")
            return

        snapshot = self.snapshots[self.current_position]
        short_id = snapshot.vertex_id.split("-")[0] if "-" in snapshot.vertex_id else snapshot.vertex_id

        print(f"\n{'=' * 80}")
        print(f"State at Step {self.current_position}: {short_id}")
        print(f"{'=' * 80}\n")

        print(f"Component: {snapshot.vertex_id}")
        print(f"Step: {snapshot.step}")

        # Show inputs
        if snapshot.inputs:
            print("\nInputs:")
            for key, value in list(snapshot.inputs.items())[:5]:
                print(f"  {key}: {str(value)[:60]}...")

        # Show outputs
        if snapshot.outputs:
            print("\nOutputs:")
            print(f"  {str(snapshot.outputs)[:200]}...")

        # Show queue
        if snapshot.queue_state_after:
            print("\nQueue at this point:")
            max_queue_display = 10
            for vid in snapshot.queue_state_after[:max_queue_display]:
                short = vid.split("-")[0] if "-" in vid else vid
                print(f"  - {short}")
            if len(snapshot.queue_state_after) > max_queue_display:
                print(f"  ... and {len(snapshot.queue_state_after) - max_queue_display} more")

        # Show run_manager state
        if snapshot.graph_state_after:
            run_pred = snapshot.graph_state_after.get("run_predecessors", {})
            waiting = {k: v for k, v in run_pred.items() if v}
            if waiting:
                print("\nComponents waiting for dependencies:")
                for comp, deps in list(waiting.items())[:5]:
                    short_comp = comp.split("-")[0] if "-" in comp else comp
                    short_deps = [d.split("-")[0] for d in deps]
                    print(f"  {short_comp} waiting for: {short_deps}")

        print()

    def next_step(self) -> bool:
        """Move to next component in timeline.

        Returns:
            True if moved, False if at end
        """
        if self.current_position < len(self.snapshots) - 1:
            self.current_position += 1
            return True
        return False

    def previous_step(self) -> bool:
        """Move to previous component in timeline.

        Returns:
            True if moved, False if at beginning
        """
        if self.current_position > 0:
            self.current_position -= 1
            return True
        return False

    def _restore_graph_state(self, graph: Any, snapshot: ComponentSnapshot) -> None:
        """Restore graph to the state captured in snapshot.

        Args:
            graph: The graph to restore
            snapshot: The snapshot to restore from
        """
        # Restore run_manager state
        if hasattr(graph, "run_manager") and snapshot.graph_state_after:
            state = snapshot.graph_state_after
            if "run_predecessors" in state:
                graph.run_manager.run_predecessors = state["run_predecessors"].copy()
            if "run_map" in state:
                graph.run_manager.run_map = state["run_map"].copy()
            if "vertices_to_run" in state:
                graph.run_manager.vertices_to_run = state["vertices_to_run"].copy()
            if "vertices_being_run" in state:
                graph.run_manager.vertices_being_run = state["vertices_being_run"].copy()

        # Restore queue
        if hasattr(graph, "_run_queue") and snapshot.queue_state_after:
            from collections import deque

            graph._run_queue = deque(snapshot.queue_state_after)  # noqa: SLF001

        # Restore context
        if hasattr(graph, "_context") and snapshot.context:
            graph._context.update(snapshot.context)  # noqa: SLF001

    def _create_mock_build_vertex(self, cached_results: dict[str, Any], original_build: Any):
        """Create a mocked build_vertex that returns cached results for upstream components.

        Args:
            cached_results: Dict mapping vertex_id to cached results
            original_build: The original build_vertex function

        Returns:
            Mocked build_vertex function
        """

        async def mocked_build_vertex(vertex_id: str, *args, **kwargs):
            # If we have a cached result for this vertex, return it
            if vertex_id in cached_results:
                print(f"  📼 Using cached result for {vertex_id.split('-')[0]}")
                return cached_results[vertex_id]

            # Otherwise execute normally
            print(f"  ▶️  Executing {vertex_id.split('-')[0]}")
            return await original_build(vertex_id, *args, **kwargs)

        return mocked_build_vertex

    def create_graph_for_replay(self) -> Any:
        """Create a fresh graph instance for replay.

        Returns:
            Graph instance ready for replay

        Raises:
            ValueError: If flow_data wasn't stored in recording
        """
        if self.flow_data is None:
            msg = "No flow data in recording. Recording must be created with record_graph()."
            raise ValueError(msg)

        from lfx.graph.graph.base import Graph

        graph = Graph.from_payload(self.flow_data)
        graph.prepare()
        return graph

    async def replay_from_here(
        self,
        graph: Any | None = None,
        *,
        modified_inputs: dict[str, Any] | None = None,
        steps: int | None = None,
    ) -> list[Any]:
        """Replay execution from current position forward.

        Args:
            graph: The graph instance to replay on
            modified_inputs: Optional modified inputs for current component
            steps: Number of steps to execute (None = all remaining)

        Returns:
            List of results from replayed components

        Example:
            # In Jupyter:
            from lfx.graph.graph.base import Graph
            graph = Graph.from_payload(...)

            recording.jump_to("LoopComponent")
            results = await recording.replay_from_here(graph, steps=5)
        """
        if self.current_position >= len(self.snapshots):
            print("❌ Already at end of recording")
            return []

        # Create graph if not provided
        if graph is None:
            print("📦 Creating graph from recording...")
            graph = self.create_graph_for_replay()

        current_snapshot = self.snapshots[self.current_position]

        print(f"🎬 Replaying from step {self.current_position}: {current_snapshot.vertex_id.split('-')[0]}")

        # 1. Restore graph state
        print("📋 Restoring graph state...")
        self._restore_graph_state(graph, current_snapshot)

        # 2. Create cached results for all upstream components
        cached_results = {}
        for i in range(self.current_position):
            snap = self.snapshots[i]
            if snap.outputs is not None:
                # Store the full result snapshot
                cached_results[snap.vertex_id] = snap.outputs

        print(f"📼 Cached {len(cached_results)} upstream results")

        # 3. Mock build_vertex to use cached results
        original_build = graph.build_vertex
        graph.build_vertex = self._create_mock_build_vertex(cached_results, original_build)

        # 4. Apply modified inputs if provided
        if modified_inputs:
            print(f"✏️  Applying {len(modified_inputs)} modified inputs")
            # TODO: Apply modified inputs to current vertex

        # 5. Execute from current position
        max_steps = steps if steps is not None else (len(self.snapshots) - self.current_position)
        print(f"▶️  Executing {max_steps} steps...\n")

        results = []
        steps_executed = 0

        try:
            # Execute via astep for step-by-step control
            while steps_executed < max_steps and graph.get_run_queue():
                result = await graph.astep(user_id=graph.user_id)

                if result and hasattr(result, "vertex"):
                    results.append(result)
                    print(f"  [{steps_executed}] Executed: {result.vertex.display_name}")

                steps_executed += 1

        finally:
            # Restore original build_vertex
            graph.build_vertex = original_build

        print(f"\n✅ Replayed {steps_executed} steps")
        return results


async def record_graph(
    flow_or_path: Any, *, method: str = "async_start", flow_name: str | None = None
) -> GraphRecording:
    """Record a graph execution for playback and debugging.

    Args:
        flow_or_path: Either a Graph object or path to flow JSON file
        method: Execution method to record
        flow_name: Optional name for the recording (auto-detected from path if not provided)

    Returns:
        GraphRecording with complete execution trace

    Examples:
        # From file
        recording = await record_graph("my_flow.json")

        # From existing graph
        from lfx.graph.graph.base import Graph
        graph = Graph.from_payload(...)
        recording = await record_graph(graph, flow_name="My Flow")
    """
    import json

    from lfx.graph.graph.base import Graph
    from lfx.graph.graph.constants import Finish

    from .trace_data import ExecutionTrace, ExecutionTracer

    # Determine if we got a Graph or a path
    if isinstance(flow_or_path, Graph):
        # Already have a graph!
        graph = flow_or_path
        graph_data = None  # Don't have original flow data
        detected_name = flow_name or graph.flow_name or "Recording"
    else:
        # Load from path
        flow_path = Path(flow_or_path)
        flow_data = json.loads(flow_path.read_text())
        graph_data = flow_data.get("data", flow_data)

        # Create graph
        graph = Graph.from_payload(graph_data)
        detected_name = flow_name or flow_path.stem

    # Trace execution
    trace = ExecutionTrace(path_name=method)
    tracer = ExecutionTracer(graph, trace)

    snapshots = []

    try:
        tracer.install()
        graph.prepare()

        # Track state before first execution
        state_before_first = {}
        queue_before_first = []

        async for result in graph.async_start():
            if isinstance(result, Finish):
                break

            if hasattr(result, "vertex"):
                # Create snapshot for this component
                vertex_id = result.vertex.id
                step = len(snapshots)

                # Get state AFTER this component executed
                graph_state_after = graph.run_manager.to_dict() if hasattr(graph, "run_manager") else {}
                queue_state_after = graph.get_run_queue() if hasattr(graph, "get_run_queue") else []
                context = dict(graph.context) if hasattr(graph, "context") else {}

                # For the "before" state, use the "after" state from previous snapshot
                if snapshots:
                    graph_state_before = snapshots[-1].graph_state_after
                    queue_state_before = snapshots[-1].queue_state_after
                else:
                    # First component - capture initial state
                    graph_state_before = state_before_first if state_before_first else graph_state_after
                    queue_state_before = queue_before_first if queue_before_first else []

                # Get component inputs/outputs
                component_inputs = {}
                if hasattr(result.vertex, "params"):
                    component_inputs = result.vertex.params.copy()

                component_outputs = result.result if hasattr(result, "result") else None

                snapshot = ComponentSnapshot(
                    vertex_id=vertex_id,
                    step=step,
                    inputs=component_inputs,
                    outputs=component_outputs,
                    graph_state_before=graph_state_before,
                    graph_state_after=graph_state_after,
                    queue_state_before=queue_state_before,
                    queue_state_after=queue_state_after,
                    context=context,
                    error=None,
                )

                snapshots.append(snapshot)

                # Capture initial state on first iteration
                if not state_before_first:
                    state_before_first = graph_state_before
                    queue_before_first = queue_state_before

    except Exception as e:  # noqa: BLE001
        # Record error in last snapshot (as string for pickle compatibility)
        if snapshots:
            snapshots[-1].error = str(e)
    finally:
        tracer.uninstall()

    recording = GraphRecording(
        flow_name=detected_name,
        execution_method=method,
        snapshots=snapshots,
        current_position=0,
        flow_data=graph_data,  # Store for replay (None if Graph was passed)
    )

    print(f"✅ Recorded {len(snapshots)} component executions")

    return recording
