"""SqliteCheckpointStore — durable CheckpointStore backend (LE-1695).

Implements the existing ``lfx.graph.checkpoint.store.CheckpointStore`` ABC on the same
single SQLite file as the job store, so one crash-safe artifact holds a run's job row,
event log, and checkpoint. Round-trips a REAL GraphCheckpoint built from a real paused
graph — not a hand-made stub — per the prefer-real-integrations policy.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph
from lfx.services.durable.sqlite_checkpoints import SqliteCheckpointStore


@pytest.fixture
def store(tmp_path):
    return SqliteCheckpointStore(tmp_path / "durable.db")


async def _real_checkpoint(job_id: str = "job-1"):
    chat_input = ChatInput(_id="chat_input", input_value="hello")
    chat_input.set(should_store_message=False)
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=chat_input.message_response, should_store_message=False)
    graph = Graph(chat_input, chat_output)
    graph.session_id = "sess-1"
    graph.set_run_id()
    graph.checkpointing_enabled = True
    graph.job_id = job_id
    await graph.astep()
    return graph.build_checkpoint()


class TestCheckpointRoundTrip:
    async def test_should_load_a_saved_checkpoint_by_id(self, store):
        checkpoint = await _real_checkpoint()

        await store.save(checkpoint)
        loaded = await store.load(checkpoint.checkpoint_id)

        assert loaded is not None
        assert loaded.checkpoint_id == checkpoint.checkpoint_id
        assert loaded.run_id == checkpoint.run_id
        assert loaded.vertex_results.keys() == checkpoint.vertex_results.keys()

    async def test_should_survive_a_process_restart(self, store, tmp_path):
        checkpoint = await _real_checkpoint()
        await store.save(checkpoint)

        reopened = SqliteCheckpointStore(tmp_path / "durable.db")

        assert await reopened.load(checkpoint.checkpoint_id) is not None

    async def test_should_load_latest_checkpoint_by_run_id(self, store):
        first = await _real_checkpoint()
        second = await _real_checkpoint()
        second.run_id = first.run_id

        await store.save(first)
        await store.save(second)

        loaded = await store.load_by_run_id(first.run_id)
        assert loaded is not None
        assert loaded.checkpoint_id == second.checkpoint_id

    async def test_should_return_none_for_unknown_ids(self, store):
        assert await store.load("nope") is None
        assert await store.load_by_run_id("nope") is None

    async def test_should_delete_a_checkpoint(self, store):
        checkpoint = await _real_checkpoint()
        await store.save(checkpoint)

        await store.delete(checkpoint.checkpoint_id)

        assert await store.load(checkpoint.checkpoint_id) is None

    async def test_should_list_checkpoints_by_session(self, store):
        checkpoint = await _real_checkpoint()
        await store.save(checkpoint)

        by_session = await store.list_by_session("sess-1")

        assert [c.checkpoint_id for c in by_session] == [checkpoint.checkpoint_id]
        assert await store.list_by_session("other") == []


class TestExpiry:
    async def test_should_not_load_an_expired_checkpoint(self, store):
        checkpoint = await _real_checkpoint()
        checkpoint.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await store.save(checkpoint)

        assert await store.load(checkpoint.checkpoint_id) is None
        assert await store.load_by_run_id(checkpoint.run_id) is None


class TestBlobs:
    async def test_should_round_trip_a_blob_per_job_and_kind(self, store):
        await store.save_blob("job-9", "agent", '{"tool_state": 1}')

        assert await store.load_blob("job-9", "agent") == '{"tool_state": 1}'
        assert await store.load_blob("job-9", "other") is None

    async def test_should_overwrite_a_blob_for_same_key(self, store):
        await store.save_blob("job-9", "agent", "v1")
        await store.save_blob("job-9", "agent", "v2")

        assert await store.load_blob("job-9", "agent") == "v2"

    async def test_blob_should_survive_restart(self, store, tmp_path):
        await store.save_blob("job-9", "agent", "persisted")

        reopened = SqliteCheckpointStore(tmp_path / "durable.db")

        assert await reopened.load_blob("job-9", "agent") == "persisted"
