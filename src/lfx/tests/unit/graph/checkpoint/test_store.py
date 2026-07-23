"""Contract tests for CheckpointStore + the in-memory reference impl (LE-1440)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from lfx.graph.checkpoint.schema import GraphCheckpoint
from lfx.graph.checkpoint.store import CheckpointStore, InMemoryCheckpointStore
from lfx.graph.exceptions import GraphPausedException


def _checkpoint(run_id: str = "run-1", session_id: str = "sess-1", **overrides) -> GraphCheckpoint:
    base = {
        "run_id": run_id,
        "flow_id": "flow-1",
        "session_id": session_id,
        "job_id": "job-1",
        "flow_payload": {"nodes": [], "edges": []},
    }
    base.update(overrides)
    return GraphCheckpoint(**base)


async def test_save_then_load_returns_same_checkpoint():
    store = InMemoryCheckpointStore()
    cp = _checkpoint()
    await store.save(cp)
    loaded = await store.load(cp.checkpoint_id)
    assert loaded == cp


async def test_load_missing_returns_none():
    store = InMemoryCheckpointStore()
    assert await store.load("nope") is None


async def test_delete_removes_checkpoint():
    store = InMemoryCheckpointStore()
    cp = _checkpoint()
    await store.save(cp)
    await store.delete(cp.checkpoint_id)
    assert await store.load(cp.checkpoint_id) is None


async def test_load_honors_expiry():
    store = InMemoryCheckpointStore()
    expired = _checkpoint(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    await store.save(expired)
    assert await store.load(expired.checkpoint_id) is None


async def test_load_by_run_id_returns_most_recent_non_expired():
    store = InMemoryCheckpointStore()
    old = _checkpoint(created_at=datetime.now(timezone.utc) - timedelta(minutes=10))
    newer = _checkpoint(created_at=datetime.now(timezone.utc) - timedelta(minutes=1))
    expired_newest = _checkpoint(
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    for cp in (old, newer, expired_newest):
        await store.save(cp)
    loaded = await store.load_by_run_id("run-1")
    assert loaded is not None
    assert loaded.checkpoint_id == newer.checkpoint_id


async def test_load_by_run_id_missing_returns_none():
    store = InMemoryCheckpointStore()
    assert await store.load_by_run_id("ghost") is None


async def test_list_by_session_returns_only_that_session():
    store = InMemoryCheckpointStore()
    a1 = _checkpoint(run_id="r1", session_id="sess-a")
    a2 = _checkpoint(run_id="r2", session_id="sess-a")
    b1 = _checkpoint(run_id="r3", session_id="sess-b")
    for cp in (a1, a2, b1):
        await store.save(cp)
    found = await store.list_by_session("sess-a")
    assert {cp.checkpoint_id for cp in found} == {a1.checkpoint_id, a2.checkpoint_id}


def test_in_memory_store_is_a_checkpoint_store():
    assert issubclass(InMemoryCheckpointStore, CheckpointStore)


def test_graph_paused_exception_carries_pause_payload():
    exc = GraphPausedException(
        checkpoint_id="cp-1",
        reason="human_input_required",
        data={"options": ["approve", "reject"]},
    )
    assert exc.checkpoint_id == "cp-1"
    assert exc.reason == "human_input_required"
    assert exc.data == {"options": ["approve", "reject"]}
    assert "cp-1" in str(exc)
