"""Comprehensive tests for graph execution recorder.

Tests the timeline navigation, state inspection, and save/load functionality.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_record_graph_creates_snapshots():
    """Test that recording captures all component executions."""
    from lfx.debug.recorder import record_graph

    recording = await record_graph("src/backend/tests/data/LoopTest.json")

    # Should have recorded multiple snapshots
    assert len(recording.snapshots) > 0, "Should capture component executions"

    # Should have flow data for replay
    assert recording.flow_data is not None, "Should store flow data"

    # Should start at position 0
    assert recording.current_position == 0, "Should start at beginning"

    # Each snapshot should have required fields
    first_snap = recording.snapshots[0]
    assert first_snap.vertex_id is not None
    assert first_snap.step == 0
    assert first_snap.inputs is not None
    assert first_snap.graph_state_before is not None
    assert first_snap.graph_state_after is not None
    assert first_snap.queue_state_before is not None
    assert first_snap.queue_state_after is not None


@pytest.mark.asyncio
async def test_timeline_navigation():
    """Test jumping to different positions in timeline."""
    from lfx.debug.recorder import record_graph

    recording = await record_graph("src/backend/tests/data/LoopTest.json")

    total_steps = len(recording.snapshots)

    # Test jump by step number
    recording.jump_to(5)
    assert recording.current_position == 5

    recording.jump_to(10)
    assert recording.current_position == 10

    # Test jump by component name
    recording.jump_to("LoopComponent")
    # Should jump to first occurrence of LoopComponent
    assert "Loop" in recording.snapshots[recording.current_position].vertex_id

    # Test next_step
    pos_before = recording.current_position
    moved = recording.next_step()
    assert moved is True
    assert recording.current_position == pos_before + 1

    # Test previous_step
    pos_before = recording.current_position
    moved = recording.previous_step()
    assert moved is True
    assert recording.current_position == pos_before - 1

    # Test bounds
    recording.jump_to(total_steps - 1)
    moved = recording.next_step()
    assert moved is False  # Can't go past end

    recording.jump_to(0)
    moved = recording.previous_step()
    assert moved is False  # Can't go before start


@pytest.mark.asyncio
async def test_find_component_occurrences():
    """Test finding all occurrences of a component."""
    from lfx.debug.recorder import record_graph

    recording = await record_graph("src/backend/tests/data/LoopTest.json")

    # Find all LoopComponent executions
    loop_steps = [i for i, snap in enumerate(recording.snapshots) if "Loop" in snap.vertex_id]

    assert len(loop_steps) > 1, "Loop should execute multiple times"

    # Jump to each and verify it's a loop
    for step in loop_steps[:3]:
        recording.jump_to(step)
        snapshot = recording.snapshots[recording.current_position]
        assert "Loop" in snapshot.vertex_id


@pytest.mark.asyncio
async def test_state_inspection_has_required_data():
    """Test that state snapshots contain all required data."""
    from lfx.debug.recorder import record_graph

    recording = await record_graph("src/backend/tests/data/LoopTest.json")

    # Jump to a loop component
    recording.jump_to("LoopComponent")
    snapshot = recording.snapshots[recording.current_position]

    # Should have inputs
    assert snapshot.inputs is not None
    assert len(snapshot.inputs) > 0

    # Should have graph state
    assert snapshot.graph_state_after is not None
    assert "run_predecessors" in snapshot.graph_state_after
    assert "run_map" in snapshot.graph_state_after

    # Should have queue state
    assert snapshot.queue_state_after is not None
    assert isinstance(snapshot.queue_state_after, list)

    # Should have context
    assert snapshot.context is not None


@pytest.mark.asyncio
async def test_save_and_load_preserves_state():
    """Test that save/load preserves recording state."""
    import tempfile

    from lfx.debug.recorder import GraphRecording, record_graph

    recording = await record_graph("src/backend/tests/data/LoopTest.json")

    # Jump to specific position
    recording.jump_to(15)
    original_position = recording.current_position
    original_snapshots = len(recording.snapshots)

    # Save
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pkl") as f:
        temp_path = f.name

    try:
        recording.save(temp_path)

        # Load
        loaded = GraphRecording.load(temp_path)

        # Verify state preserved
        assert loaded.current_position == original_position
        assert len(loaded.snapshots) == original_snapshots
        assert loaded.flow_name == recording.flow_name
        assert loaded.execution_method == recording.execution_method
        assert loaded.flow_data is not None

    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_compare_queue_across_loop_iterations():
    """Test comparing state across multiple loop iterations."""
    from lfx.debug.recorder import record_graph

    recording = await record_graph("src/backend/tests/data/LoopTest.json")

    # Find all loop iterations
    loop_steps = [i for i, snap in enumerate(recording.snapshots) if "Loop" in snap.vertex_id]

    assert len(loop_steps) >= 5, "Should have multiple loop iterations"

    # Compare queue at first vs last iteration
    recording.jump_to(loop_steps[0])
    first_queue = recording.snapshots[recording.current_position].queue_state_after

    recording.jump_to(loop_steps[-1])
    last_queue = recording.snapshots[recording.current_position].queue_state_after

    # Both should have queue state
    assert first_queue is not None
    assert last_queue is not None

    # Queue contents may differ (expected)
    # This test just verifies we can access and compare them


@pytest.mark.asyncio
async def test_context_contains_loop_state():
    """Test that context snapshots contain loop state."""
    from lfx.debug.recorder import record_graph

    recording = await record_graph("src/backend/tests/data/LoopTest.json")

    # Find a loop execution
    loop_steps = [i for i, snap in enumerate(recording.snapshots) if "Loop" in snap.vertex_id]

    assert len(loop_steps) > 0, "Should have loop executions"

    # Check that context has loop-specific data
    recording.jump_to(loop_steps[1])  # Second iteration
    snapshot = recording.snapshots[recording.current_position]

    # Context should exist
    assert snapshot.context is not None

    # Should contain loop-specific keys
    loop_id = snapshot.vertex_id
    # Keys like "{loop_id}_index", "{loop_id}_data", etc.
    context_keys = snapshot.context.keys()
    has_loop_keys = any(loop_id in str(key) for key in context_keys)

    assert has_loop_keys, f"Context should contain loop-specific keys. Got: {list(context_keys)[:5]}"


@pytest.mark.asyncio
async def test_replay_creates_new_graph():
    """Test that replay can create a fresh graph when needed."""
    from lfx.debug.recorder import record_graph

    recording = await record_graph("src/backend/tests/data/LoopTest.json")

    # Jump to middle
    recording.jump_to(10)

    # Replay without providing graph - should create one
    results = await recording.replay_from_here(steps=2)

    # Should return results
    assert isinstance(results, list)
    # May be empty or have results depending on graph state


@pytest.mark.asyncio
async def test_recording_captures_errors():
    """Test that errors during execution are captured."""
    # This would need a flow that intentionally fails
    # For now, just verify the error field exists
    from lfx.debug.recorder import record_graph

    recording = await record_graph("src/backend/tests/data/LoopTest.json")

    # Check that snapshots have error field
    for snapshot in recording.snapshots:
        assert hasattr(snapshot, "error")
        # For LoopTest.json, all should succeed
        assert snapshot.error is None


@pytest.mark.asyncio
async def test_multiple_recordings_independent():
    """Test that multiple recordings don't interfere with each other."""
    from lfx.debug.recorder import record_graph

    # Record same flow twice
    recording1 = await record_graph("src/backend/tests/data/LoopTest.json")
    recording2 = await record_graph("src/backend/tests/data/LoopTest.json")

    # Navigate independently
    recording1.jump_to(5)
    recording2.jump_to(10)

    assert recording1.current_position == 5
    assert recording2.current_position == 10

    # Should have same number of snapshots
    assert len(recording1.snapshots) == len(recording2.snapshots)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
