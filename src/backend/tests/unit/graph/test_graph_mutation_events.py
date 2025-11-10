"""Tests for graph mutation event system."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from lfx.debug.events import GraphMutationEvent


@pytest.mark.asyncio
async def test_queue_operations_emit_events():
    """Test queue operations emit before/after events."""
    from lfx.graph.graph.base import Graph

    events = []

    async def capture(event: GraphMutationEvent):
        events.append(event)

    graph = Graph()
    graph.register_observer(capture)
    await graph.extend_run_queue(["v1", "v2"])

    assert len(events) == 2
    assert events[0].timing == "before"
    assert events[1].timing == "after"


@pytest.mark.asyncio
async def test_dependency_updates_both_structures():
    """Test add_dynamic_dependency updates both structures."""
    from lfx.graph.graph.base import Graph

    graph = Graph()
    await graph.add_dynamic_dependency("v1", "v2")

    assert "v2" in graph.run_manager.run_predecessors["v1"]
    assert "v1" in graph.run_manager.run_map["v2"]


@pytest.mark.asyncio
async def test_fast_path_no_overhead():
    """Test zero overhead without observers."""
    from lfx.graph.graph.base import Graph

    graph = Graph()
    await graph.extend_run_queue(["v1"])
    assert graph._mutation_step == 0
