"""Tests for graph mutation event system.

These tests verify that the centralized mutation system correctly emits events
and maintains state consistency.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_queue_operations_emit_events():
    """Test that queue operations emit before/after events."""
    from lfx.debug.events import GraphMutationEvent
    from lfx.graph.graph.base import Graph

    events = []

    async def capture_events(event: GraphMutationEvent):
        events.append(event)

    graph = Graph()
    graph.register_observer(capture_events)

    # Extend queue should emit 2 events (before + after)
    await graph.extend_run_queue(["vertex1", "vertex2"])

    assert len(events) == 2
    assert events[0].event_type == "queue_extended"
    assert events[0].timing == "before"
    assert events[1].timing == "after"
    assert events[1].changes["added"] == ["vertex1", "vertex2"]


@pytest.mark.asyncio
async def test_dependency_operations_emit_events():
    """Test that add_dynamic_dependency emits events."""
    from lfx.debug.events import GraphMutationEvent
    from lfx.graph.graph.base import Graph

    events = []

    async def capture_events(event: GraphMutationEvent):
        events.append(event)

    graph = Graph()
    graph.register_observer(capture_events)

    # Add dependency should emit 2 events
    await graph.add_dynamic_dependency("vertex1", "vertex2")

    assert len(events) == 2
    assert events[0].event_type == "dependency_added"
    assert events[0].timing == "before"
    assert events[1].timing == "after"

    # Should update both run_predecessors and run_map
    assert "vertex1" in events[1].changes
    assert "vertex2" in events[1].changes["predecessor"]


@pytest.mark.asyncio
async def test_vertex_state_changes_emit_events():
    """Test that marking vertices emits events."""
    from lfx.debug.events import GraphMutationEvent
    from lfx.graph.graph.base import Graph
    from lfx.graph.vertex.base import VertexStates

    events = []

    async def capture_events(event: GraphMutationEvent):
        events.append(event)

    # Create a graph with a vertex
    from lfx import components as cp

    comp = cp.ChatInput()
    graph = Graph(comp, comp)
    graph.prepare()

    graph.register_observer(capture_events)

    # Mark vertex should emit 2 events
    vertex_id = graph.vertices[0].id
    await graph.mark_vertex(vertex_id, VertexStates.INACTIVE)

    assert len(events) >= 2
    marked_events = [e for e in events if e.event_type == "vertex_marked"]
    assert len(marked_events) == 2
    assert marked_events[0].timing == "before"
    assert marked_events[1].timing == "after"


@pytest.mark.asyncio
async def test_events_are_serializable():
    """Test that events can be serialized for replay."""
    from lfx.debug.events import GraphMutationEvent
    from lfx.graph.graph.base import Graph

    events = []

    async def capture_events(event: GraphMutationEvent):
        events.append(event)

    graph = Graph()
    graph.register_observer(capture_events)

    await graph.extend_run_queue(["v1"])

    # Test serialization
    event = events[0]
    serialized = event.to_dict()

    assert isinstance(serialized, dict)
    assert "event_type" in serialized
    assert "state_before" in serialized
    assert "state_after" in serialized

    # Test deserialization
    restored = GraphMutationEvent.from_dict(serialized)
    assert restored.event_type == event.event_type
    assert restored.timing == event.timing


@pytest.mark.asyncio
async def test_observer_errors_collected():
    """Test that observer errors are logged and collected."""
    from lfx.graph.graph.base import Graph

    async def failing_observer(event):
        raise ValueError("Observer error!")

    graph = Graph()
    graph.register_observer(failing_observer)

    # This should not crash, just collect error
    await graph.extend_run_queue(["v1"])

    errors = graph.get_observer_errors()
    assert len(errors) >= 1
    assert isinstance(errors[0][0], ValueError)


@pytest.mark.asyncio
async def test_no_events_when_no_observers():
    """Test zero overhead fast path when no observers."""
    from lfx.graph.graph.base import Graph

    graph = Graph()

    # Should be disabled
    assert graph._enable_events is False

    # Fast path should be used
    await graph.extend_run_queue(["v1"])

    # No events tracked
    assert graph._mutation_step == 0


@pytest.mark.asyncio
async def test_events_enabled_when_observer_registered():
    """Test that events auto-enable when observer registered."""
    from lfx.graph.graph.base import Graph

    graph = Graph()
    assert graph._enable_events is False

    async def dummy_observer(event):
        pass

    graph.register_observer(dummy_observer)
    assert graph._enable_events is True

    graph.unregister_observer(dummy_observer)
    assert graph._enable_events is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
