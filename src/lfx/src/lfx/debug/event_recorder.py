"""Event-based graph recorder using pure observer pattern.

This recorder observes graph mutation events instead of wrapping build_vertex.
"""

# ruff: noqa: T201

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lfx.debug.events import GraphMutationEvent

__all__ = ["EventBasedRecording", "EventRecorder"]


@dataclass
class EventBasedRecording:
    """Recording built from mutation events (pure observer pattern)."""

    flow_name: str
    events: list[Any] = field(default_factory=list)  # GraphMutationEvent list
    component_executions: list[str] = field(default_factory=list)  # Vertex IDs

    def get_events_for_vertex(self, vertex_id: str) -> list[Any]:
        """Get all events related to a specific vertex."""
        return [e for e in self.events if e.vertex_id == vertex_id]

    def get_events_by_type(self, event_type: str) -> list[Any]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def get_queue_evolution(self) -> list[dict[str, Any]]:
        """Get how queue changed over time."""
        queue_events = self.get_events_by_type("queue_extended") + self.get_events_by_type("queue_dequeued")
        queue_events.sort(key=lambda e: e.step)

        return [
            {
                "step": event.step,
                "event": event.event_type,
                "queue": event.state_after.get("queue", []),
                "changes": event.changes,
            }
            for event in queue_events
            if event.timing == "after"
        ]

    def get_dependency_changes(self) -> list[dict[str, Any]]:
        """Get all dependency modifications."""
        dep_events = self.get_events_by_type("dependency_added")

        return [
            {
                "step": event.step,
                "vertex": event.vertex_id,
                "predecessor": event.changes.get("predecessor"),
                "run_predecessors_changed": event.changes.get("run_predecessors_changed"),
                "run_map_changed": event.changes.get("run_map_changed"),
            }
            for event in dep_events
            if event.timing == "after"
        ]

    def show_summary(self) -> None:
        """Display summary of recording."""
        print(f"\n{'=' * 80}")
        print(f"Event Recording: {self.flow_name}")
        print(f"{'=' * 80}\n")
        print(f"Total events: {len(self.events)}")
        print(f"Components executed: {len(set(self.component_executions))}")

        # Count by type
        by_type = {}
        for event in self.events:
            by_type[event.event_type] = by_type.get(event.event_type, 0) + 1

        print("\nEvent types:")
        for event_type, count in sorted(by_type.items()):
            print(f"  {event_type}: {count}")


class EventRecorder:
    """Records graph execution by observing mutation events (pure observer)."""

    def __init__(self, flow_name: str = "Recording"):
        self.flow_name = flow_name
        self.events: list[GraphMutationEvent] = []
        self.component_executions: list[str] = []

    async def on_event(self, event: GraphMutationEvent) -> None:
        """Observer callback - receives all graph mutations.

        Args:
            event: GraphMutationEvent from graph
        """
        self.events.append(event)

        # Track component executions
        if event.vertex_id and event.vertex_id not in self.component_executions:
            self.component_executions.append(event.vertex_id)

    def get_recording(self) -> EventBasedRecording:
        """Build recording from collected events.

        Returns:
            EventBasedRecording with all events
        """
        return EventBasedRecording(
            flow_name=self.flow_name, events=self.events, component_executions=self.component_executions
        )


async def record_graph_with_events(graph: Any, flow_name: str = "Recording") -> EventBasedRecording:
    """Record graph execution using pure observer pattern.

    Args:
        graph: Graph instance to record
        flow_name: Name for the recording

    Returns:
        EventBasedRecording with complete event log

    Example:
        from lfx.graph.graph.base import Graph
        from lfx.debug.event_recorder import record_graph_with_events

        graph = Graph(...)
        recording = await record_graph_with_events(graph, "My Flow")

        # Analyze events
        print(f"Total events: {len(recording.events)}")
        recording.show_summary()
    """
    recorder = EventRecorder(flow_name)
    graph.register_observer(recorder.on_event)

    try:
        # Execute graph
        from lfx.graph.graph.constants import Finish

        async for result in graph.async_start():
            if isinstance(result, Finish):
                break

    finally:
        graph.unregister_observer(recorder.on_event)

    return recorder.get_recording()
