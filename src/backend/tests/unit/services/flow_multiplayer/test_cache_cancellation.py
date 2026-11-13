"""A cancelled request never leaves a cached graph wrong: no database, the real engines, injected cancellation.

- A catch-up cancelled while its replay runs in a worker thread: the replay finishes and the entry's
  revision moves with it, in one step, so the graph and its revision still agree.
- A write cancelled while its batch is being staged: the batch is dropped and the entry evicted.
- A write cancelled after its commit, while it waits to keep the batch: the batch is kept and the
  entry's revision moves with it before the entry is evicted.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import orjson
import pytest
from langflow.services.flow_multiplayer import cache, oplog, writes
from langflow.services.flow_multiplayer.cache import CACHE, FlowEntry

FIELD_PATH = ["data", "node", "template", "t", "value"]
SLOW = 0.3


def _graph() -> bytes:
    node = {"id": "a", "data": {"node": {"display_name": "a", "template": {"t": {"value": "v0"}}}}}
    return orjson.dumps({"nodes": [node], "edges": []})


def _set(value: str) -> dict:
    return {"type": "update_nodes", "updates": [{"op": "set_field", "id": "a", "path": FIELD_PATH, "value": value}]}


def _value(state: Any) -> str:
    return orjson.loads(state.to_json())["nodes"][0]["data"]["node"]["template"]["t"]["value"]


class SlowState:
    """A GraphState whose replay and stages take SLOW seconds first, to cancel the caller meanwhile."""

    def __init__(self, state: Any) -> None:
        self._state = state

    def replay(self, *args: Any, **kwargs: Any) -> Any:
        time.sleep(SLOW)
        return self._state.replay(*args, **kwargs)

    def stage(self, *args: Any, **kwargs: Any) -> Any:
        time.sleep(SLOW)
        return self._state.stage(*args, **kwargs)

    def stage_json(self, *args: Any, **kwargs: Any) -> Any:
        time.sleep(SLOW)
        return self._state.stage_json(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._state, name)


@pytest.fixture(params=["python", "rust"])
def engine(request):
    from lfx.services.flow_operations.engine import get_engine

    return get_engine(request.param)


async def _cancel_after(coro: Any, delay: float) -> None:
    task = asyncio.ensure_future(coro)
    await asyncio.sleep(delay)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_cancelled_catch_up_keeps_graph_and_revision_together(engine, monkeypatch):
    count = 70  # at least LARGE_OPS_COUNT: the replay runs in a worker thread
    encoded = [orjson.dumps(_set(f"v{i}")) for i in range(1, count + 1)]
    envelope = oplog.envelope_text(
        encoded, start=1, request_id=str(uuid.uuid4()), actor_id=uuid.uuid4(), operations_sha256="x"
    )
    rows = [oplog.LogRow(1, count, envelope)]

    async def rows_after(*_args: Any, **_kwargs: Any) -> list[oplog.LogRow]:
        return rows

    monkeypatch.setattr(oplog, "rows_after", rows_after)
    entry = FlowEntry(uuid.uuid4(), SlowState(engine.GraphState(_graph())), 0)
    await _cancel_after(cache.catch_up(None, entry, count), SLOW / 3)
    # The replay finished in its thread; the revision moved in the same step.
    assert entry.revision == count
    assert _value(entry.state) == f"v{count}"


async def test_cancelled_stage_drops_the_batch_and_evicts_the_entry(engine):
    flow_id = uuid.uuid4()
    entry = FlowEntry(flow_id, SlowState(engine.GraphState(_graph())), 0)  # new: its first stage is large
    CACHE.put(entry)

    class Session:
        async def commit(self) -> None:  # never reached
            raise AssertionError

    request = writes.OpsRequest(
        request_id=str(uuid.uuid4()), base_revision=0, operations_json=orjson.dumps([_set("x")]), count=1
    )
    try:
        await _cancel_after(
            writes._write_cached(Session(), flow_id, uuid.uuid4(), request, "sha", 0, mode="wal"), SLOW / 3
        )
        assert CACHE.get(flow_id) is None
        assert not entry.state.staged
        assert _value(entry.state) == "v0"
    finally:
        CACHE.evict(flow_id)


async def test_cancelled_keep_after_commit_keeps_the_batch_with_its_revision(engine, monkeypatch):
    flow_id = uuid.uuid4()
    entry = FlowEntry(flow_id, engine.GraphState(_graph()), 0)
    entry.new = False  # a small inline stage
    CACHE.put(entry)

    async def append_rows(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(oplog, "append_rows", append_rows)
    monkeypatch.setattr(writes, "_rows", lambda forward, head: [(head + 1, head + len(forward), [b"{}"])])

    class Session:
        async def commit(self) -> None:
            # Another call holds the graph when the commit returns, so keeping waits for it.
            await entry.use.acquire()
            asyncio.get_running_loop().call_later(SLOW, entry.use.release)

    request = writes.OpsRequest(
        request_id=str(uuid.uuid4()), base_revision=0, operations_json=orjson.dumps([_set("x")]), count=1
    )
    try:
        await _cancel_after(
            writes._write_cached(Session(), flow_id, uuid.uuid4(), request, "sha", 0, mode="wal"), SLOW / 3
        )
        # The committed batch was kept and the revision moved in the same step, then the entry evicted.
        assert not entry.state.staged
        assert entry.revision == 1
        assert _value(entry.state) == "x"
        assert CACHE.get(flow_id) is None
    finally:
        CACHE.evict(flow_id)
