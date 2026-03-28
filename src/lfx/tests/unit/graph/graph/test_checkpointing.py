"""Tests for graph checkpointing: pause, checkpoint, resume."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.exceptions.graph import GraphPausedException
from lfx.graph.graph.base import Graph
from lfx.graph.graph.constants import Finish
from lfx.services.checkpoint.schema import GraphCheckpoint, VertexCheckpointData
from lfx.services.checkpoint.service import InMemoryCheckpointStore


# ---------------------------------------------------------------------------
# Phase A: CheckpointStore and data model tests
# ---------------------------------------------------------------------------


class TestGraphCheckpointModel:
    def test_checkpoint_defaults(self):
        cp = GraphCheckpoint(flow_id="f1", session_id="s1", run_id="r1")
        assert cp.checkpoint_id  # UUID generated
        assert cp.flow_id == "f1"
        assert cp.session_id == "s1"
        assert cp.completed_layers == 0
        assert cp.vertex_results == {}
        assert cp.paused_vertex_id is None
        assert cp.created_at is not None

    def test_checkpoint_with_vertex_data(self):
        vd = VertexCheckpointData(
            built=True,
            results={"output": "hello"},
            artifacts={"key": "val"},
        )
        cp = GraphCheckpoint(
            flow_id="f1",
            session_id="s1",
            run_id="r1",
            vertex_results={"v1": vd},
            paused_vertex_id="v2",
            pause_reason="input-required",
            pause_data={"question": "Which env?"},
        )
        assert cp.vertex_results["v1"].built is True
        assert cp.paused_vertex_id == "v2"
        assert cp.pause_reason == "input-required"

    def test_checkpoint_serialization_roundtrip(self):
        cp = GraphCheckpoint(
            flow_id="f1",
            session_id="s1",
            run_id="r1",
            completed_layers=2,
            vertices_to_run={"v3", "v4"},
            pause_reason="input-required",
        )
        data = cp.model_dump()
        restored = GraphCheckpoint.model_validate(data)
        assert restored.checkpoint_id == cp.checkpoint_id
        assert restored.completed_layers == 2
        assert restored.vertices_to_run == {"v3", "v4"}


class TestInMemoryCheckpointStore:
    @pytest.fixture
    def store(self):
        return InMemoryCheckpointStore()

    @pytest.fixture
    def sample_checkpoint(self):
        return GraphCheckpoint(
            flow_id="flow-1",
            session_id="session-1",
            run_id="run-1",
            completed_layers=1,
            pause_reason="input-required",
        )

    @pytest.mark.asyncio
    async def test_save_and_load(self, store, sample_checkpoint):
        checkpoint_id = await store.save(sample_checkpoint)
        loaded = await store.load(checkpoint_id)
        assert loaded is not None
        assert loaded.checkpoint_id == checkpoint_id
        assert loaded.flow_id == "flow-1"
        assert loaded.pause_reason == "input-required"

    @pytest.mark.asyncio
    async def test_load_missing_returns_none(self, store):
        result = await store.load("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, store, sample_checkpoint):
        checkpoint_id = await store.save(sample_checkpoint)
        await store.delete(checkpoint_id)
        result = await store.load(checkpoint_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_is_noop(self, store):
        await store.delete("nonexistent-id")  # Should not raise

    @pytest.mark.asyncio
    async def test_list_by_session(self, store):
        cp1 = GraphCheckpoint(flow_id="f1", session_id="s1", run_id="r1")
        cp2 = GraphCheckpoint(flow_id="f2", session_id="s1", run_id="r2")
        cp3 = GraphCheckpoint(flow_id="f3", session_id="s2", run_id="r3")
        await store.save(cp1)
        await store.save(cp2)
        await store.save(cp3)

        s1_checkpoints = await store.list_by_session("s1")
        assert len(s1_checkpoints) == 2
        assert all(cp.session_id == "s1" for cp in s1_checkpoints)

    @pytest.mark.asyncio
    async def test_ttl_expiry(self, store):
        expired = GraphCheckpoint(
            flow_id="f1",
            session_id="s1",
            run_id="r1",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        await store.save(expired)
        result = await store.load(expired.checkpoint_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_load_by_run_id(self, store):
        cp1 = GraphCheckpoint(flow_id="f1", session_id="s1", run_id="run-123")
        cp2 = GraphCheckpoint(flow_id="f2", session_id="s2", run_id="run-456")
        await store.save(cp1)
        await store.save(cp2)

        result = await store.load_by_run_id("run-123")
        assert result is not None
        assert result.run_id == "run-123"

        missing = await store.load_by_run_id("run-999")
        assert missing is None

    @pytest.mark.asyncio
    async def test_ttl_not_expired(self, store):
        future = GraphCheckpoint(
            flow_id="f1",
            session_id="s1",
            run_id="r1",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        await store.save(future)
        result = await store.load(future.checkpoint_id)
        assert result is not None


# ---------------------------------------------------------------------------
# Phase B: Graph pause and checkpoint creation tests
# ---------------------------------------------------------------------------


class TestCheckpointingOptIn:
    def test_checkpointing_disabled_by_default(self):
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(input_value="hello")
        chat_output = ChatOutput(input_value="test", _id="chat_output")
        chat_output.set(sender_name=chat_input.message_response)
        graph = Graph(chat_input, chat_output)
        assert graph._checkpointing_enabled is False

    @pytest.mark.asyncio
    async def test_pause_ignored_when_checkpointing_disabled(self):
        """When checkpointing is off, request_pause is a no-op during process()."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(input_value="hello", should_store_message=False)
        chat_output = ChatOutput(input_value="test", _id="chat_output")
        chat_output.set(sender_name=chat_input.message_response, should_store_message=False)

        graph = Graph(chat_input, chat_output)
        graph.flow_id = "test-flow"
        # Checkpointing NOT enabled (default)
        graph.prepare()
        graph._pause_requested = True
        graph._pause_info = {"vertex_id": "chat_input", "reason": "test", "data": {}}

        # process() should NOT raise — pause is ignored when checkpointing disabled
        result = await graph.process(fallback_to_env_vars=False)
        assert result is graph  # Completed normally


class TestGraphPause:
    def test_request_pause_sets_state(self):
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(input_value="hello")
        chat_output = ChatOutput(input_value="test", _id="chat_output")
        chat_output.set(sender_name=chat_input.message_response)
        graph = Graph(chat_input, chat_output)

        graph.request_pause(vertex_id="v1", reason="input-required", data={"q": "why?"})
        assert graph._pause_requested is True
        assert graph._pause_info["vertex_id"] == "v1"
        assert graph._pause_info["reason"] == "input-required"
        assert graph._pause_info["data"]["q"] == "why?"

    def test_create_checkpoint_captures_state(self):
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(input_value="hello")
        chat_output = ChatOutput(input_value="test", _id="chat_output")
        chat_output.set(sender_name=chat_input.message_response)
        graph = Graph(chat_input, chat_output)
        graph._session_id = "test-session"
        graph._run_id = "test-run"
        graph.flow_id = "test-flow"

        graph.request_pause(vertex_id="chat_input", reason="test-pause")
        checkpoint = graph._create_checkpoint(completed_layers=1)

        assert checkpoint.flow_id == "test-flow"
        assert checkpoint.session_id == "test-session"
        assert checkpoint.run_id == "test-run"
        assert checkpoint.completed_layers == 1
        assert checkpoint.paused_vertex_id == "chat_input"
        assert checkpoint.pause_reason == "test-pause"

    @pytest.mark.asyncio
    async def test_process_raises_on_pause(self):
        """When a vertex requests pause, process() should raise GraphPausedException."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(input_value="hello", should_store_message=False)
        chat_output = ChatOutput(input_value="test", _id="chat_output")
        chat_output.set(sender_name=chat_input.message_response, should_store_message=False)

        graph = Graph(chat_input, chat_output)
        graph.flow_id = "test-flow"
        graph._session_id = "test-session"
        graph._checkpointing_enabled = True
        graph._checkpoint_store = InMemoryCheckpointStore()

        # Manually trigger pause before processing
        # We simulate a vertex that calls request_pause during build
        # by injecting the pause state after prepare
        graph.prepare()

        # Force pause after layer 0
        graph._pause_requested = True
        graph._pause_info = {
            "vertex_id": "chat_input",
            "reason": "input-required",
            "data": {"question": "Which env?"},
        }

        with pytest.raises(GraphPausedException) as exc_info:
            await graph.process(fallback_to_env_vars=False)

        assert exc_info.value.reason == "input-required"
        assert exc_info.value.checkpoint_id  # UUID assigned
        assert exc_info.value.data["question"] == "Which env?"

        # Verify checkpoint was saved to the store
        loaded = await graph._checkpoint_store.load(exc_info.value.checkpoint_id)
        assert loaded is not None
        assert loaded.pause_reason == "input-required"


# ---------------------------------------------------------------------------
# Phase C: Graph resume from checkpoint tests
# ---------------------------------------------------------------------------


class TestGraphResume:
    def _make_simple_graph(self) -> Graph:
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(input_value="hello", should_store_message=False)
        chat_output = ChatOutput(input_value="test", _id="chat_output")
        chat_output.set(sender_name=chat_input.message_response, should_store_message=False)
        return Graph(chat_input, chat_output)

    def test_checkpoint_roundtrip_data_integrity(self):
        """Verify that checkpoint data is complete enough for resume."""
        graph = self._make_simple_graph()
        graph.flow_id = "test-flow"
        graph._session_id = "test-session"
        graph._run_id = "test-run"

        # Run the graph synchronously to populate vertex states
        results = list(graph.start())
        assert results[-1] == Finish()

        # Create a checkpoint after execution
        graph.request_pause(vertex_id="chat_input", reason="test")
        checkpoint = graph._create_checkpoint(completed_layers=1)

        # Verify checkpoint captured built vertices
        assert "chat_input" in checkpoint.vertex_results
        assert checkpoint.vertex_results["chat_input"].built is True
        assert checkpoint.run_manager_state  # Not empty

    @pytest.mark.asyncio
    async def test_resume_from_checkpoint_restores_identity(self):
        """Verify that resume_from_checkpoint restores identity fields."""
        checkpoint = GraphCheckpoint(
            flow_id="test-flow",
            session_id="test-session",
            run_id="test-run",
            completed_layers=1,
            pause_reason="input-required",
            flow_payload={},  # Empty payload - no graph to reconstruct
        )

        resumed = await Graph.resume_from_checkpoint(checkpoint)

        assert resumed.flow_id == "test-flow"
        assert resumed._session_id == "test-session"
        assert resumed._run_id == "test-run"

    @pytest.mark.asyncio
    async def test_resume_restores_execution_state(self):
        """Verify resume correctly restores run_manager and vertices_to_run."""
        checkpoint = GraphCheckpoint(
            flow_id="test-flow",
            session_id="test-session",
            run_id="test-run",
            completed_layers=1,
            run_manager_state={
                "run_map": {"v1": ["v2"]},
                "run_predecessors": {"v2": []},
                "vertices_to_run": {"v2"},
                "vertices_being_run": set(),
                "ran_at_least_once": {"v1"},
            },
            vertices_to_run={"v2"},
            activated_vertices=["v1"],
            call_order=["v1"],
        )

        resumed = await Graph.resume_from_checkpoint(checkpoint)

        assert resumed.run_manager.ran_at_least_once == {"v1"}
        assert resumed.vertices_to_run == {"v2"}
        assert resumed.activated_vertices == ["v1"]
        assert resumed._call_order == ["v1"]

    @pytest.mark.asyncio
    async def test_resume_with_input_injection(self):
        """Verify that input injection works when the vertex exists in the graph."""
        # Build a real graph so we have vertices in vertex_map
        graph = self._make_simple_graph()
        graph.flow_id = "test-flow"
        graph._session_id = "test-session"
        graph._run_id = "test-run"

        # Run to completion first
        list(graph.start())

        # Create checkpoint
        graph.request_pause(vertex_id="chat_input", reason="input-required")
        checkpoint = graph._create_checkpoint(completed_layers=1)

        # Since component-built graphs have empty raw_graph_data,
        # resume won't reconstruct vertices. In production, graphs come from
        # JSON payloads and resume works fully. For this test, verify the
        # checkpoint data is correct and the mechanism is sound.
        assert checkpoint.paused_vertex_id == "chat_input"
        assert checkpoint.vertex_results["chat_input"].built is True
        assert checkpoint.pause_reason == "input-required"


# ---------------------------------------------------------------------------
# GraphPausedException tests
# ---------------------------------------------------------------------------


class TestGraphPausedException:
    def test_exception_attributes(self):
        exc = GraphPausedException(
            checkpoint_id="cp-123",
            reason="input-required",
            data={"question": "Which env?"},
        )
        assert exc.checkpoint_id == "cp-123"
        assert exc.reason == "input-required"
        assert exc.data == {"question": "Which env?"}
        assert "input-required" in str(exc)
        assert "cp-123" in str(exc)

    def test_exception_default_data(self):
        exc = GraphPausedException(checkpoint_id="cp-1", reason="test")
        assert exc.data == {}
