"""Tests for graph checkpoint save/restore functionality."""

import json
from collections import deque

import pytest
from lfx.components.input_output import ChatInput, ChatOutput, TextOutputComponent
from lfx.graph import Graph
from lfx.graph.graph.constants import Finish


class TestGraphCheckpoint:
    """Tests for graph snapshot and restore functionality."""

    @pytest.mark.asyncio
    async def test_get_graph_snapshot_captures_state(self):
        """Test that _get_graph_snapshot captures all relevant state."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(sender_name=chat_input.message_response)

        graph = Graph(chat_input, chat_output)

        # Run first step
        await graph.astep()

        # Take snapshot
        snapshot = graph._get_graph_snapshot()

        # Verify snapshot contains expected keys
        assert "run_manager" in snapshot
        assert "queue" in snapshot
        assert "vertices_layers" in snapshot
        assert "context" in snapshot
        assert "inactivated_vertices" in snapshot
        assert "activated_vertices" in snapshot
        assert "conditionally_excluded" in snapshot
        assert "mutation_step" in snapshot

        # Verify queue state (after first step, chat_output should be in queue)
        assert snapshot["queue"] == ["chat_output"]

    @pytest.mark.asyncio
    async def test_restore_from_snapshot_restores_queue(self):
        """Test that restore_from_snapshot correctly restores the run queue."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)

        # Initial queue should be chat_input
        assert graph._run_queue == deque(["chat_input"])

        # Run first step (processes chat_input)
        await graph.astep()

        # Take snapshot after first step
        snapshot_after_step1 = graph._get_graph_snapshot()
        queue_after_step1 = list(graph._run_queue)

        # Run second step
        await graph.astep()

        # Queue should have changed
        assert list(graph._run_queue) != queue_after_step1

        # Restore to checkpoint
        graph.restore_from_snapshot(snapshot_after_step1)

        # Queue should be back to post-step1 state
        assert list(graph._run_queue) == queue_after_step1

    @pytest.mark.asyncio
    async def test_checkpoint_and_resume_execution(self):
        """Test full checkpoint/resume cycle - graph completes correctly after restore."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)

        # Run first step
        await graph.astep()

        # Take checkpoint
        checkpoint = graph._get_graph_snapshot()

        # Complete the graph
        results_first_run = [result async for result in graph.async_start()]

        # Verify first run completed
        assert results_first_run[-1] == Finish()

        # Now restore and run again from checkpoint
        graph.restore_from_snapshot(checkpoint)

        # Run from checkpoint to completion
        results_from_checkpoint = [result async for result in graph.async_start()]

        # Both runs should complete
        assert results_from_checkpoint[-1] == Finish()

        # Both should have same number of results (from checkpoint point)
        assert len(results_first_run) == len(results_from_checkpoint)

    @pytest.mark.asyncio
    async def test_snapshot_preserves_context(self):
        """Test that graph context is preserved across checkpoint/restore."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(sender_name=chat_input.message_response)

        graph = Graph(chat_input, chat_output)

        # Set some context
        graph.context["test_key"] = "test_value"
        graph.context["another_key"] = 42

        # Take snapshot
        snapshot = graph._get_graph_snapshot()

        # Modify context
        graph.context["test_key"] = "modified"
        graph.context["new_key"] = "new_value"

        # Restore
        graph.restore_from_snapshot(snapshot)

        # Context should be restored
        assert graph.context["test_key"] == "test_value"
        assert graph.context["another_key"] == 42
        assert "new_key" not in graph.context

    @pytest.mark.asyncio
    async def test_snapshot_preserves_mutation_step(self):
        """Test that mutation step counter is preserved through checkpoint/restore."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)

        # Manually set mutation step (normally incremented by event system)
        graph._mutation_step = 42

        # Take snapshot
        snapshot = graph._get_graph_snapshot()

        # Verify snapshot captured mutation step
        assert snapshot["mutation_step"] == 42

        # Modify mutation step
        graph._mutation_step = 100

        # Restore
        graph.restore_from_snapshot(snapshot)

        # Mutation step should be restored
        assert graph._mutation_step == 42

    @pytest.mark.asyncio
    async def test_restore_preserves_vertex_activation_states(self):
        """Test that vertex activation states are preserved."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)

        # Run first step
        await graph.astep()

        # Capture activation states
        inactivated = set(graph.inactivated_vertices)
        activated = list(graph.activated_vertices)

        # Take snapshot
        snapshot = graph._get_graph_snapshot()

        # Run more steps to change activation states
        await graph.astep()

        # Restore
        graph.restore_from_snapshot(snapshot)

        # Verify activation states restored
        assert set(graph.inactivated_vertices) == inactivated
        assert list(graph.activated_vertices) == activated


class TestCheckpointPersistence:
    """Tests for checkpoint serialization/deserialization (DB persistence simulation)."""

    @pytest.mark.asyncio
    async def test_snapshot_is_json_serializable(self):
        """Test that graph snapshot can be serialized to JSON without custom encoder."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)

        # Run first step
        await graph.astep()

        # Take snapshot
        snapshot = graph._get_graph_snapshot()

        # This should not raise - snapshot should be natively JSON-serializable
        # (no default=str needed - sets converted to lists, etc.)
        json_str = json.dumps(snapshot)
        assert json_str is not None
        assert len(json_str) > 0

    @pytest.mark.asyncio
    async def test_snapshot_roundtrip_json_serialization(self):
        """Test that snapshot survives JSON serialization roundtrip."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)

        # Add some context data
        graph.context["user_data"] = {"name": "test", "count": 42}

        # Run first step
        await graph.astep()

        # Take snapshot
        snapshot = graph._get_graph_snapshot()

        # Serialize and deserialize (simulating DB storage)
        # No default=str needed - snapshot is natively JSON-serializable
        json_str = json.dumps(snapshot)
        restored_snapshot = json.loads(json_str)

        # restore_from_snapshot handles list->set conversion internally
        graph.restore_from_snapshot(restored_snapshot)

        # Verify context was preserved through JSON roundtrip
        assert graph.context["user_data"]["name"] == "test"
        assert graph.context["user_data"]["count"] == 42

    @pytest.mark.asyncio
    async def test_persist_and_resume_execution(self):
        """Test complete persist/resume cycle: run, checkpoint, serialize, deserialize, resume."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)

        # Run first step
        await graph.astep()
        queue_after_step1 = list(graph._run_queue)

        # Take snapshot and serialize to JSON (simulating DB write)
        snapshot = graph._get_graph_snapshot()
        json_str = json.dumps(snapshot)  # No default=str needed

        # Complete original execution
        results_original = [result async for result in graph.async_start()]
        assert results_original[-1] == Finish()

        # Now simulate loading from DB and resuming
        restored_snapshot = json.loads(json_str)

        # Restore checkpoint (list->set conversion handled internally)
        graph.restore_from_snapshot(restored_snapshot)

        # Verify queue was restored
        assert list(graph._run_queue) == queue_after_step1

        # Resume execution from checkpoint
        results_resumed = [result async for result in graph.async_start()]

        # Both should complete successfully
        assert results_resumed[-1] == Finish()
        # Both should have same number of steps from checkpoint
        assert len(results_original) == len(results_resumed)

    @pytest.mark.asyncio
    async def test_snapshot_with_complex_context_data(self):
        """Test that complex context data survives persistence."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(sender_name=chat_input.message_response)

        graph = Graph(chat_input, chat_output)

        # Add complex nested context data
        graph.context["nested"] = {
            "level1": {
                "level2": {
                    "value": "deep_value",
                    "list": [1, 2, 3],
                }
            }
        }
        graph.context["simple_list"] = ["a", "b", "c"]
        graph.context["number"] = 123.456

        # Snapshot and roundtrip
        snapshot = graph._get_graph_snapshot()
        json_str = json.dumps(snapshot)  # No default=str needed
        restored = json.loads(json_str)

        # Clear context and restore (list->set conversion handled internally)
        graph._context = {}
        graph.restore_from_snapshot(restored)

        # Verify complex data survived
        assert graph.context["nested"]["level1"]["level2"]["value"] == "deep_value"
        assert graph.context["nested"]["level1"]["level2"]["list"] == [1, 2, 3]
        assert graph.context["simple_list"] == ["a", "b", "c"]
        assert graph.context["number"] == 123.456


class TestCheckpointValidation:
    """Tests for checkpoint validation and error handling."""

    def test_restore_from_snapshot_missing_required_keys(self):
        """Test that restoring from snapshot with missing keys raises ValueError."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(sender_name=chat_input.message_response)

        graph = Graph(chat_input, chat_output)

        # Missing run_manager
        invalid_snapshot = {"queue": ["chat_input"]}
        with pytest.raises(ValueError, match="missing required keys"):
            graph.restore_from_snapshot(invalid_snapshot)

        # Missing queue
        invalid_snapshot = {"run_manager": {}}
        with pytest.raises(ValueError, match="missing required keys"):
            graph.restore_from_snapshot(invalid_snapshot)

    def test_restore_from_snapshot_invalid_vertex_ids(self):
        """Test that restoring snapshot with non-existent vertices raises error."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(sender_name=chat_input.message_response)

        graph = Graph(chat_input, chat_output)

        # Take valid snapshot
        snapshot = graph._get_graph_snapshot()

        # Modify queue to include non-existent vertex
        snapshot["queue"] = ["nonexistent_vertex"]

        with pytest.raises(ValueError, match=r"vertices.*not found"):
            graph.restore_from_snapshot(snapshot)

    def test_restore_from_snapshot_mixed_valid_invalid_vertices(self):
        """Test that restoring with mix of valid and invalid vertices raises error."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)

        # Take valid snapshot
        snapshot = graph._get_graph_snapshot()

        # Queue has valid and invalid vertex
        snapshot["queue"] = ["text_output", "fake_vertex"]

        with pytest.raises(ValueError, match=r"fake_vertex.*not found"):
            graph.restore_from_snapshot(snapshot)
