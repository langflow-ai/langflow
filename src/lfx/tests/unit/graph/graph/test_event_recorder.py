"""Tests for event-based graph recorder (pure observer pattern)."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_event_recorder_captures_all_mutations():
    """Test that event recorder captures all graph mutations."""
    import json
    from pathlib import Path

    from lfx.debug.event_recorder import record_graph_with_events
    from lfx.graph.graph.base import Graph

    test_file = Path(__file__).parent.parent.parent.parent / "data" / "LoopTest.json"
    data = json.loads(test_file.read_text())

    graph = Graph.from_payload(data["data"])

    recording = await record_graph_with_events(graph, "Test")

    # Should capture many events
    assert len(recording.events) > 100

    # Should have queue and vertex events
    queue_events = recording.get_events_by_type("queue_extended")
    assert len(queue_events) > 0

    vertex_events = recording.get_events_by_type("vertex_marked")
    assert len(vertex_events) > 0


@pytest.mark.asyncio
async def test_queue_evolution_tracking():
    """Test queue evolution analysis."""
    import json
    from pathlib import Path

    from lfx.debug.event_recorder import record_graph_with_events
    from lfx.graph.graph.base import Graph

    test_file = Path(__file__).parent.parent.parent.parent / "data" / "LoopTest.json"
    data = json.loads(test_file.read_text())

    graph = Graph.from_payload(data["data"])
    recording = await record_graph_with_events(graph, "Test")

    queue_evo = recording.get_queue_evolution()

    # Should have queue evolution entries
    assert len(queue_evo) > 0

    # Each entry should have required fields
    first = queue_evo[0]
    assert "step" in first
    assert "queue" in first
    assert "changes" in first


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
