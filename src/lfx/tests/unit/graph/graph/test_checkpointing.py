"""Tests for graph checkpointing: pause, checkpoint, resume.

Tests are organized by layer:
  1. Data model and store (GraphCheckpoint, InMemoryCheckpointStore)
  2. Graph mechanics (request_pause, _create_checkpoint, opt-in gating)
  3. Integration (real graph execution → pause → checkpoint → resume)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.exceptions.graph import GraphPausedException
from lfx.graph.graph.base import Graph, _deserialize_vertex_value, _serialize_vertex_value
from lfx.graph.graph.constants import Finish
from lfx.services.checkpoint.schema import GraphCheckpoint, VertexCheckpointData
from lfx.services.checkpoint.service import InMemoryCheckpointStore


# ---------------------------------------------------------------------------
# 1. Data model and store
# ---------------------------------------------------------------------------


class TestGraphCheckpointModel:
    def test_checkpoint_defaults(self):
        cp = GraphCheckpoint(flow_id="f1", session_id="s1", run_id="r1")
        assert cp.checkpoint_id  # UUID generated
        assert cp.flow_id == "f1"
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
        assert cp.vertex_results["v1"].results == {"output": "hello"}
        assert cp.paused_vertex_id == "v2"
        assert cp.pause_data["question"] == "Which env?"

    def test_checkpoint_serialization_roundtrip(self):
        """model_dump → model_validate must preserve all fields including sets."""
        cp = GraphCheckpoint(
            flow_id="f1",
            session_id="s1",
            run_id="r1",
            completed_layers=2,
            vertices_to_run={"v3", "v4"},
            inactivated_vertices={"v5"},
            pause_reason="input-required",
        )
        data = cp.model_dump()
        restored = GraphCheckpoint.model_validate(data)
        assert restored.checkpoint_id == cp.checkpoint_id
        assert restored.completed_layers == 2
        assert restored.vertices_to_run == {"v3", "v4"}
        assert restored.inactivated_vertices == {"v5"}

    def test_checkpoint_json_roundtrip(self):
        """JSON serialization must also roundtrip (important for DB storage)."""
        cp = GraphCheckpoint(
            flow_id="f1",
            session_id="s1",
            run_id="r1",
            vertices_to_run={"a", "b"},
            vertex_results={
                "v1": VertexCheckpointData(built=True, results={"x": 1}),
            },
        )
        json_str = cp.model_dump_json()
        restored = GraphCheckpoint.model_validate_json(json_str)
        assert restored.vertices_to_run == {"a", "b"}
        assert restored.vertex_results["v1"].built is True
        assert restored.vertex_results["v1"].results == {"x": 1}


class TestInMemoryCheckpointStore:
    @pytest.fixture
    def store(self):
        return InMemoryCheckpointStore()

    def _make_checkpoint(self, **kwargs) -> GraphCheckpoint:
        defaults = {"flow_id": "f1", "session_id": "s1", "run_id": "r1"}
        defaults.update(kwargs)
        return GraphCheckpoint(**defaults)

    @pytest.mark.asyncio
    async def test_save_and_load(self, store):
        cp = self._make_checkpoint(pause_reason="input-required")
        checkpoint_id = await store.save(cp)
        loaded = await store.load(checkpoint_id)
        assert loaded is not None
        assert loaded.checkpoint_id == checkpoint_id
        assert loaded.pause_reason == "input-required"

    @pytest.mark.asyncio
    async def test_load_missing_returns_none(self, store):
        assert await store.load("nonexistent-id") is None

    @pytest.mark.asyncio
    async def test_delete(self, store):
        cp = self._make_checkpoint()
        checkpoint_id = await store.save(cp)
        await store.delete(checkpoint_id)
        assert await store.load(checkpoint_id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_is_noop(self, store):
        await store.delete("nonexistent-id")  # Should not raise

    @pytest.mark.asyncio
    async def test_list_by_session(self, store):
        await store.save(self._make_checkpoint(session_id="s1", run_id="r1"))
        await store.save(self._make_checkpoint(session_id="s1", run_id="r2"))
        await store.save(self._make_checkpoint(session_id="s2", run_id="r3"))

        result = await store.list_by_session("s1")
        assert len(result) == 2
        assert all(cp.session_id == "s1" for cp in result)

    @pytest.mark.asyncio
    async def test_load_by_run_id(self, store):
        await store.save(self._make_checkpoint(run_id="run-123"))
        await store.save(self._make_checkpoint(run_id="run-456"))

        result = await store.load_by_run_id("run-123")
        assert result is not None
        assert result.run_id == "run-123"
        assert await store.load_by_run_id("run-999") is None

    @pytest.mark.asyncio
    async def test_load_by_run_id_returns_most_recent(self, store):
        """When multiple checkpoints exist for a run, return the newest."""
        old = self._make_checkpoint(
            run_id="run-1",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            completed_layers=1,
        )
        new = self._make_checkpoint(
            run_id="run-1",
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            completed_layers=2,
        )
        await store.save(old)
        await store.save(new)

        result = await store.load_by_run_id("run-1")
        assert result is not None
        assert result.completed_layers == 2

    @pytest.mark.asyncio
    async def test_ttl_expiry_on_load(self, store):
        expired = self._make_checkpoint(
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        await store.save(expired)
        assert await store.load(expired.checkpoint_id) is None

    @pytest.mark.asyncio
    async def test_ttl_expiry_on_load_by_run_id(self, store):
        expired = self._make_checkpoint(
            run_id="run-expired",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        await store.save(expired)
        assert await store.load_by_run_id("run-expired") is None

    @pytest.mark.asyncio
    async def test_ttl_not_expired(self, store):
        future = self._make_checkpoint(
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        await store.save(future)
        assert await store.load(future.checkpoint_id) is not None


# ---------------------------------------------------------------------------
# 2. Graph mechanics
# ---------------------------------------------------------------------------


def _make_graph() -> Graph:
    """Build a minimal 2-vertex graph (ChatInput → ChatOutput)."""
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(input_value="hello", should_store_message=False)
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(sender_name=chat_input.message_response, should_store_message=False)
    return Graph(chat_input, chat_output)


class TestVertexValueSerialization:
    def test_none_roundtrips(self):
        assert _serialize_vertex_value(None) is None
        assert _deserialize_vertex_value(None) is None

    def test_primitives_roundtrip(self):
        assert _serialize_vertex_value("hello") == "hello"
        assert _serialize_vertex_value(42) == 42
        assert _serialize_vertex_value({"a": [1, 2]}) == {"a": [1, 2]}

    def test_non_serializable_returns_none(self):
        assert _serialize_vertex_value(object()) is None
        assert _serialize_vertex_value(lambda: None) is None

    def test_pydantic_model_roundtrips(self):
        from lfx.schema.message import Message

        msg = Message(text="hello", sender="User", sender_name="User")
        serialized = _serialize_vertex_value(msg)
        assert serialized is not None
        assert serialized["__pydantic__"] is True
        assert serialized["__class__"] == "Message"

        restored = _deserialize_vertex_value(serialized)
        assert isinstance(restored, Message)
        assert restored.text == "hello"

    def test_dict_of_pydantic_models_roundtrips(self):
        """built_object is typically {'message': Message(...)}."""
        from lfx.schema.message import Message

        msg = Message(text="world", sender="AI", sender_name="AI")
        built_obj = {"message": msg}

        serialized = _serialize_vertex_value(built_obj)
        assert serialized is not None
        assert serialized["message"]["__pydantic__"] is True

        restored = _deserialize_vertex_value(serialized)
        assert isinstance(restored["message"], Message)
        assert restored["message"].text == "world"

    def test_dict_with_non_serializable_value_returns_none(self):
        """If any value in a dict can't be serialized, entire dict returns None."""
        built_obj = {"good": "value", "bad": object()}
        assert _serialize_vertex_value(built_obj) is None


class TestCheckpointingOptIn:
    def test_checkpointing_disabled_by_default(self):
        graph = _make_graph()
        assert graph._checkpointing_enabled is False

    @pytest.mark.asyncio
    async def test_pause_ignored_when_checkpointing_disabled(self):
        """process() completes normally even if _pause_requested is set."""
        graph = _make_graph()
        graph.flow_id = "test-flow"
        graph.prepare()
        graph._pause_requested = True
        graph._pause_info = {"vertex_id": "chat_input", "reason": "test", "data": {}}

        result = await graph.process(fallback_to_env_vars=False)
        assert result is graph


class TestRequestPause:
    def test_sets_pause_state(self):
        graph = _make_graph()
        graph.request_pause(vertex_id="v1", reason="input-required", data={"q": "why?"})

        assert graph._pause_requested is True
        assert graph._pause_info["vertex_id"] == "v1"
        assert graph._pause_info["reason"] == "input-required"
        assert graph._pause_info["data"]["q"] == "why?"

    def test_default_data_is_empty_dict(self):
        graph = _make_graph()
        graph.request_pause(vertex_id="v1", reason="test")
        assert graph._pause_info["data"] == {}


class TestCreateCheckpoint:
    def test_captures_identity_and_pause_context(self):
        graph = _make_graph()
        graph.flow_id = "test-flow"
        graph._session_id = "test-session"
        graph._run_id = "test-run"
        graph.request_pause(vertex_id="chat_input", reason="test-pause")

        checkpoint = graph._create_checkpoint(completed_layers=1)

        assert checkpoint.flow_id == "test-flow"
        assert checkpoint.session_id == "test-session"
        assert checkpoint.run_id == "test-run"
        assert checkpoint.completed_layers == 1
        assert checkpoint.paused_vertex_id == "chat_input"
        assert checkpoint.pause_reason == "test-pause"

    def test_sets_expiration(self):
        graph = _make_graph()
        graph.flow_id = "f"
        graph._session_id = "s"
        graph._run_id = "r"
        graph.request_pause(vertex_id="v", reason="test")

        checkpoint = graph._create_checkpoint(completed_layers=0)
        assert checkpoint.expires_at is not None
        assert checkpoint.expires_at > datetime.now(timezone.utc)

    def test_captures_built_vertex_results(self):
        """After running a graph, checkpoint should capture built vertex state."""
        graph = _make_graph()
        graph.flow_id = "f"
        graph._session_id = "s"
        graph._run_id = "r"

        # Actually run the graph
        results = list(graph.start())
        assert results[-1] == Finish()

        graph.request_pause(vertex_id="chat_input", reason="test")
        checkpoint = graph._create_checkpoint(completed_layers=1)

        assert "chat_input" in checkpoint.vertex_results
        assert checkpoint.vertex_results["chat_input"].built is True
        assert "chat_output" in checkpoint.vertex_results
        assert checkpoint.vertex_results["chat_output"].built is True

    def test_raises_on_non_serializable_built_object(self):
        """Non-serializable built_object must raise TypeError — fail fast on data loss."""
        graph = _make_graph()
        graph.flow_id = "f"
        graph._session_id = "s"
        graph._run_id = "r"

        list(graph.start())

        # Inject a non-serializable object into a vertex
        vertex = graph.get_vertex("chat_input")
        vertex.built_object = object()  # Not JSON-serializable, not a sentinel

        graph.request_pause(vertex_id="chat_input", reason="test")
        with pytest.raises(TypeError, match="not serializable"):
            graph._create_checkpoint(completed_layers=1)


# ---------------------------------------------------------------------------
# 3. Integration: real graph execution → pause → checkpoint → resume
# ---------------------------------------------------------------------------


class TestProcessPauseIntegration:
    @pytest.mark.asyncio
    async def test_process_raises_and_saves_checkpoint(self):
        """Full flow: enable checkpointing, set pause flag, run process().
        Verify GraphPausedException is raised and checkpoint is persisted."""
        graph = _make_graph()
        graph.flow_id = "test-flow"
        graph._session_id = "test-session"
        graph._checkpointing_enabled = True

        store = InMemoryCheckpointStore()
        graph._checkpoint_store = store

        graph.prepare()
        graph._pause_requested = True
        graph._pause_info = {
            "vertex_id": "chat_input",
            "reason": "input-required",
            "data": {"question": "Which env?"},
        }

        with pytest.raises(GraphPausedException) as exc_info:
            await graph.process(fallback_to_env_vars=False)

        exc = exc_info.value
        assert exc.reason == "input-required"
        assert exc.data["question"] == "Which env?"
        assert exc.checkpoint_id

        # Checkpoint must be in the store
        loaded = await store.load(exc.checkpoint_id)
        assert loaded is not None
        assert loaded.pause_reason == "input-required"
        assert loaded.flow_id == "test-flow"

        # Checkpoint must also be findable by run_id
        by_run = await store.load_by_run_id(loaded.run_id)
        assert by_run is not None
        assert by_run.checkpoint_id == loaded.checkpoint_id


class TestResumeFromCheckpoint:
    @pytest.mark.asyncio
    async def test_restores_identity_fields(self):
        checkpoint = GraphCheckpoint(
            flow_id="test-flow",
            session_id="test-session",
            run_id="test-run",
            completed_layers=1,
            pause_reason="input-required",
            flow_payload={},
        )

        resumed = await Graph.resume_from_checkpoint(checkpoint)

        assert resumed.flow_id == "test-flow"
        assert resumed._session_id == "test-session"
        assert resumed._run_id == "test-run"

    @pytest.mark.asyncio
    async def test_restores_run_manager_state(self):
        checkpoint = GraphCheckpoint(
            flow_id="f",
            session_id="s",
            run_id="r",
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
    async def test_checkpoint_from_real_execution(self):
        """Run a graph, checkpoint it, verify checkpoint data is plausible for resume."""
        graph = _make_graph()
        graph.flow_id = "test-flow"
        graph._session_id = "test-session"
        graph._run_id = "test-run"

        results = list(graph.start())
        assert results[-1] == Finish()

        graph.request_pause(vertex_id="chat_input", reason="input-required")
        checkpoint = graph._create_checkpoint(completed_layers=1)

        # Checkpoint captured both built vertices
        assert checkpoint.vertex_results["chat_input"].built is True
        assert checkpoint.vertex_results["chat_output"].built is True
        # Run manager state is populated
        assert checkpoint.run_manager_state
        assert "run_map" in checkpoint.run_manager_state


# ---------------------------------------------------------------------------
# GraphPausedException
# ---------------------------------------------------------------------------


class TestGraphPausedException:
    def test_attributes(self):
        exc = GraphPausedException(
            checkpoint_id="cp-123",
            reason="input-required",
            data={"question": "Which env?"},
        )
        assert exc.checkpoint_id == "cp-123"
        assert exc.reason == "input-required"
        assert exc.data == {"question": "Which env?"}

    def test_string_representation(self):
        exc = GraphPausedException(checkpoint_id="cp-123", reason="input-required")
        assert "input-required" in str(exc)
        assert "cp-123" in str(exc)

    def test_default_data(self):
        exc = GraphPausedException(checkpoint_id="cp-1", reason="test")
        assert exc.data == {}

    def test_is_exception(self):
        exc = GraphPausedException(checkpoint_id="cp-1", reason="test")
        assert isinstance(exc, Exception)
