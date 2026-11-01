"""Per-process cache of loaded flow graphs (modes ``cache`` and ``wal``), LRU by flow.

Each entry holds one engine ``GraphState`` and the revision it holds, which
is always a committed revision. Two asyncio locks guard it:

- ``write``: held by a sequence that changes the graph, from catching up to
  keeping or dropping the staged batch (a writer holds it through its
  database commit). Catching up for a reader takes it too.
- ``use``: held around every call on the ``GraphState``, so no call runs
  while another runs in a worker thread (the Rust object refuses a
  concurrent borrow; the Python object would race).

While a batch is staged, ``to_json()`` returns the committed graph, so a
reader serializes the entry's revision while a writer waits for its commit,
and never sees a revision that is not committed. Mode ``cache`` writes the
staged graph to ``Flow.data`` with ``to_json(staged=True)`` before its commit.
Serialization for readers is coalesced: one ``to_json`` per revision, shared
by concurrent readers.

Which engine calls run in a worker thread (both engines alike): building a
graph from ``Flow.data``, ``to_json``, a catch-up replay of at least
``LARGE_OPS_COUNT`` operations or ``LARGE_OPS_BYTES`` bytes, whole-flow calls
(validate, repair, diff, hash), and the first batch on a newly built graph
(the engine checks the whole graph before its first batch). A batch's
``stage``, ``keep`` and ``drop`` and a small catch-up run inline.
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from typing import TYPE_CHECKING, Any

import anyio
import orjson

from langflow.services.flow_multiplayer import bench, config, oplog

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


class EntryGoneError(Exception):
    """The cached graph is ahead of the log (only after a database reset): rebuild it."""


def is_large(payload: bytes, count: int) -> bool:
    return len(payload) >= config.LARGE_OPS_BYTES or count >= config.LARGE_OPS_COUNT


async def call(function: Any, *args: Any, large: bool, **kwargs: Any) -> Any:
    """Run an engine call in a worker thread when it is large, inline otherwise (both engines alike)."""
    if large:
        return await anyio.to_thread.run_sync(lambda: function(*args, **kwargs))
    return function(*args, **kwargs)


class FlowEntry:
    __slots__ = ("flow_id", "json", "json_task", "new", "revision", "state", "use", "write")

    def __init__(self, flow_id: UUID, state: Any, revision: int) -> None:
        self.flow_id = flow_id
        self.state = state
        self.revision = revision
        self.write = asyncio.Lock()
        self.use = asyncio.Lock()
        self.json: tuple[int, str] | None = None
        self.json_task: tuple[int, asyncio.Task] | None = None
        # Built and not yet given a batch: the engine checks the whole graph before the first one.
        self.new = True

    async def replay(self, operations: list[Any]) -> None:
        payload = orjson.dumps(operations)
        large = is_large(payload, len(operations))
        async with self.use:
            await call(self.state.replay, payload, large=large)

    async def serialized(self) -> tuple[int, str]:
        """The JSON text of the entry's committed revision, one serialization per revision."""
        while True:
            revision = self.revision
            if self.json is not None and self.json[0] == revision:
                return self.json
            if self.json_task is None or self.json_task[0] != revision or self.json_task[1].done():
                task = asyncio.ensure_future(self._serialize(revision))
                self.json_task = (revision, task)
            else:
                task = self.json_task[1]
            result = await asyncio.shield(task)
            if result is not None:
                return result

    async def _serialize(self, revision: int) -> tuple[int, str] | None:
        async with self.use:
            if self.revision != revision:
                return None
            with bench.timed("ser"):
                text = await call(self.state.to_json, large=True)
        if self.revision == revision:
            self.json = (revision, text)
        return revision, text


class FlowCache:
    def __init__(self) -> None:
        self._entries: OrderedDict[UUID, FlowEntry] = OrderedDict()
        self._loading: dict[UUID, asyncio.Future] = {}

    def get(self, flow_id: UUID) -> FlowEntry | None:
        entry = self._entries.get(flow_id)
        if entry is not None:
            self._entries.move_to_end(flow_id)
        return entry

    def put(self, entry: FlowEntry) -> None:
        self._entries[entry.flow_id] = entry
        self._entries.move_to_end(entry.flow_id)
        while len(self._entries) > config.cache_max_flows():
            self._entries.popitem(last=False)

    def evict(self, flow_id: UUID, entry: FlowEntry | None = None) -> None:
        current = self._entries.get(flow_id)
        if current is not None and (entry is None or current is entry):
            del self._entries[flow_id]

    def clear(self) -> None:
        self._entries.clear()

    async def load(self, session: AsyncSession, flow_id: UUID) -> FlowEntry | None:
        """The flow's entry, built from ``Flow.data`` when it is not cached; one build per flow at a time."""
        entry = self.get(flow_id)
        if entry is not None:
            return entry
        loading = self._loading.get(flow_id)
        if loading is not None:
            return await asyncio.shield(loading)
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._loading[flow_id] = future
        try:
            entry = await build_entry(session, flow_id)
        except BaseException as exc:
            future.set_exception(exc)
            future.exception()  # mark retrieved for waiters that never come
            raise
        else:
            if entry is not None:
                self.put(entry)
            future.set_result(entry)
        finally:
            del self._loading[flow_id]
        return entry


async def build_entry(session: AsyncSession, flow_id: UUID) -> FlowEntry | None:
    """A new entry from ``Flow.data`` at ``Flow.current_revision`` (one statement)."""
    with bench.timed("load"):
        data = await oplog.read_flow_data(session, flow_id)
        if data is None:
            return None
        text = data.data if data.data is not None else '{"nodes":[],"edges":[]}'
        state = await call(config.engine().GraphState, text.encode(), large=True)
    return FlowEntry(flow_id, state, data.current_revision)


async def catch_up(session: AsyncSession, entry: FlowEntry, head: int) -> None:
    """Replay the log rows after the entry's revision through ``head``. The caller holds ``entry.write``.

    Raises ``oplog.LogGapError`` when the rows are no longer there (compacted).
    """
    if entry.revision >= head:
        return
    t0 = time.perf_counter()
    rows = await oplog.rows_after(session, entry.flow_id, entry.revision, through=head)
    revisions = oplog.revisions_of(rows, entry.revision, through=head)
    await entry.replay([operation for _, operation in revisions])
    entry.revision = head
    entry.json = None
    bench.add("catchup", (time.perf_counter() - t0) * 1000)
    bench.add("catchup_n", len(revisions))


async def entry_at_head(session: AsyncSession, flow_id: UUID, head: int) -> FlowEntry | None:
    """The flow's entry caught up to ``head``, for a reader: takes and releases ``entry.write``.

    Rebuilds the entry when the rows it needs were compacted away.
    """
    for _attempt in range(3):
        entry = await CACHE.load(session, flow_id)
        if entry is None:
            return None
        if entry.revision >= head:
            # Already there: no need to wait for a writer's commit.
            return entry
        try:
            async with entry.write:
                # A revision newer than this reader's head is committed too: serve it.
                await catch_up(session, entry, head)
        except (oplog.LogGapError, EntryGoneError):
            CACHE.evict(flow_id, entry)
        else:
            return entry
    msg = f"could not load flow {flow_id} at revision {head}"
    raise RuntimeError(msg)


CACHE = FlowCache()
