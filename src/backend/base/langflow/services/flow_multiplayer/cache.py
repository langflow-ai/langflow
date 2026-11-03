"""Per-process cache of loaded flow graphs (modes ``cache`` and ``wal``), LRU by flow.

Each entry holds one engine ``GraphState`` and the revision it holds, which
is always a committed revision. Two asyncio locks guard it:

- ``write``: held by a sequence that changes the graph, from catching up to
  keeping or dropping the staged batch (a writer holds it through its
  database commit). Catching up for a reader takes it too.
- ``use``: held around every call on the ``GraphState``, so no call runs
  while another runs in a worker thread (the Rust object refuses a
  concurrent borrow; the Python object would race). Serializing for readers
  and checkpoints takes only a snapshot under ``use`` (``GraphState.snapshot``)
  and works on it after ``use`` is released; a checkpoint hashes the text.

While a batch is staged, ``to_json()`` returns the committed graph, so a
reader serializes the entry's revision while a writer waits for its commit,
and never sees a revision that is not committed. Mode ``cache`` writes the
staged graph to ``Flow.data`` with ``to_json(staged=True)`` before its commit.
Serialization is coalesced while consumers are in flight. Text is released
after the last response or checkpoint consumer finishes; idle entries keep only the graph.

Which engine calls run in a worker thread (both engines alike): building a
graph from ``Flow.data``, ``to_json``, a catch-up replay of at least
``LARGE_OPS_COUNT`` operations or ``LARGE_OPS_BYTES`` bytes, whole-flow calls
(validate, repair, diff, equality), the SHA-256 of a checkpoint's text, and the
first batch on a newly built graph (the engine checks the whole graph before its first batch). A batch's
``stage``, ``keep`` and ``drop`` and a small catch-up run inline.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self

import anyio
import orjson

from langflow.services.flow_multiplayer import bench, config, oplog

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


class EntryGoneError(Exception):
    """The cached graph is ahead of the log (only after a database reset): rebuild it."""


def text_hash(text: str | bytes) -> str:
    """A checkpoint's hash: the SHA-256 (hex) of the exact JSON text its row stores, as UTF-8 bytes."""
    return hashlib.sha256(text.encode() if isinstance(text, str) else text).hexdigest()


def is_large(payload: bytes, count: int) -> bool:
    return len(payload) >= config.LARGE_OPS_BYTES or count >= config.LARGE_OPS_COUNT


async def call(function: Any, *args: Any, large: bool, name: str, **kwargs: Any) -> Any:
    """Run an engine call in a worker thread when it is large, inline otherwise (both engines alike).

    Records ``eng_<name>`` (wall) and ``eng_<name>_cpu`` (the running thread's CPU) on the request.
    """
    if large:
        return await uncancellable(anyio.to_thread.run_sync(lambda: bench.engine_call(name, function, *args, **kwargs)))
    return bench.engine_call(name, function, *args, **kwargs)


async def whole_flow(name: str, *args: Any, **kwargs: Any) -> Any:
    """Run the engine function ``name`` on whole flows in a worker thread (both engines alike).

    For the legacy save path (``validate``, ``repair``, ``ops_diff``, ``graph_hash``,
    ``graphs_equal``, ``apply``): each call reads or builds a whole graph, so it is large.
    Records ``eng_<name>`` on the request.
    """
    return await call(getattr(config.engine(), name), *args, large=True, name=name, **kwargs)


async def uncancellable(awaitable: Any) -> Any:
    """Await a worker-thread engine call, or a step that must finish once begun, even when the caller is cancelled.

    A thread cannot be stopped: an asyncio task cancelled while it awaits a thread returns at
    once and the thread runs on. The caller would then release the entry's locks (or record a
    revision) while the engine still works on the graph. So a cancelled caller waits for the
    thread, then raises ``CancelledError``.
    """
    future = asyncio.ensure_future(awaitable)
    try:
        return await asyncio.shield(future)
    except asyncio.CancelledError:
        while not future.done():
            try:
                await asyncio.wait([future])
            except asyncio.CancelledError:
                continue
        if not future.cancelled():
            future.exception()  # retrieved: the caller is cancelled and does not want the result
        raise


@dataclass
class _Serialization:
    revision: int
    task: asyncio.Task[tuple[int, str, float] | None] | None = None
    users: int = 0


class SerializedGraph:
    """One consumer of shared committed text. Closing the last lease releases it."""

    __slots__ = ("_entry", "_record", "owns_serialization")

    def __init__(self, entry: FlowEntry, record: _Serialization, *, owner: bool) -> None:
        self._entry: FlowEntry | None = entry
        self._record: _Serialization | None = record
        self.owns_serialization = owner
        record.users += 1

    @property
    def result(self) -> tuple[int, str, float]:
        record = self._record
        if record is None or record.task is None:
            msg = "The graph serialization lease is closed."
            raise RuntimeError(msg)
        value = record.task.result()
        if value is None:
            msg = "The graph revision changed before its snapshot was taken."
            raise RuntimeError(msg)
        return value

    @property
    def revision(self) -> int:
        return self.result[0]

    @property
    def text(self) -> str:
        return self.result[1]

    @property
    def cpu(self) -> float:
        return self.result[2]

    def close(self) -> None:
        """Release this consumer exactly once; it never cancels worker-thread work."""
        entry, record = self._entry, self._record
        self._entry = self._record = None
        if entry is not None and record is not None:
            record.users -= 1
            entry.release_serialization(record)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        self.close()


class FlowEntry:
    __slots__ = ("_serialization", "flow_id", "new", "revision", "state", "use", "write")

    def __init__(self, flow_id: UUID, state: Any, revision: int) -> None:
        self.flow_id = flow_id
        self.state = state
        self.revision = revision
        self.write = asyncio.Lock()
        self.use = asyncio.Lock()
        # Only current-revision in-flight consumers keep a record here. Older
        # revisions belong to their outstanding leases, never to an idle cache.
        self._serialization: _Serialization | None = None
        self.new = True

    def invalidate_serialized(self) -> None:
        """Detach the old revision without cancelling consumers or worker threads.

        Call on the event-loop thread after moving the revision under ``use``.
        Existing readers own their old leases; new readers must use the new head.
        """
        record = self._serialization
        if record is not None and record.revision != self.revision:
            self._serialization = None

    def release_serialization(self, record: _Serialization) -> None:
        task = record.task
        if record.users == 0 and task is not None and task.done():
            if self._serialization is record:
                self._serialization = None
            record.task = None

    def _serialization_done(self, record: _Serialization, task: asyncio.Task) -> None:
        # A sole waiter may have been cancelled while the shielded work ran.
        # Retrieve its exception without consuming it for any remaining waiter.
        if not task.cancelled():
            task.exception()
        self.release_serialization(record)

    async def replay(self, operations: list[Any], revision: int) -> None:
        """Replay and move revision together, including when the caller is cancelled."""
        payload = orjson.dumps(operations)
        large = is_large(payload, len(operations))

        def replay_and_move() -> None:
            self.state.replay(payload)
            self.revision = revision

        async with self.use:
            try:
                await call(replay_and_move, large=large, name="replay")
            finally:
                # Task ownership changes only on the event loop, not the worker.
                self.invalidate_serialized()

    async def serialized(self) -> SerializedGraph:
        """Lease shared text until the consumer finishes, including response sending.

        Concurrent consumers of one committed revision share a serialization even
        after its worker finishes. No text remains cached after the last lease.
        """
        while True:
            revision = self.revision
            record = self._serialization
            owner = (
                record is None
                or record.revision != revision
                or (record.users == 0 and record.task is not None and record.task.done())
            )
            if owner:
                record = _Serialization(revision)
                task = asyncio.ensure_future(self._serialize(revision))
                record.task = task
                self._serialization = record
                task.add_done_callback(lambda done, record=record: self._serialization_done(record, done))
            else:
                task = record.task
                if task is None:
                    # The last lease released this result before this call.
                    self._serialization = None
                    continue
            lease = SerializedGraph(self, record, owner=owner)
            try:
                result = await asyncio.shield(task)
            except BaseException:
                lease.close()
                raise
            if result is not None:
                return lease
            lease.close()

    @asynccontextmanager
    async def text_and_hash(self) -> AsyncIterator[tuple[int, str, float, bool, str, float]]:
        """Lease one revision's text through checkpoint hashing and storage.

        The caller keeps this context open through the database write. Only the
        checkpoint which starts serialization owns its serialization CPU cost.
        """
        async with await self.serialized() as serialized:
            text = serialized.text
            digest, hash_cpu = await call(bench.engine_call_cpu, text_hash, text, large=True, name="hash")
            yield (serialized.revision, text, serialized.cpu, serialized.owns_serialization, digest, hash_cpu)

    async def _serialize(self, revision: int) -> tuple[int, str, float] | None:
        """Take a committed snapshot under ``use`` and serialize after releasing it."""
        async with self.use:
            if self.revision != revision:
                return None
            snapshot = bench.engine_call("snapshot", self.state.snapshot)
        with bench.timed("ser"):
            text, cpu = await call(bench.engine_call_cpu, snapshot.to_json, large=True, name="to_json")
        return revision, text, cpu


class FlowCache:
    def __init__(self) -> None:
        self._entries: OrderedDict[UUID, FlowEntry] = OrderedDict()
        self._loading: dict[UUID, asyncio.Future] = {}
        # Flows whose entry the LRU keeps past the size limit: writers are queued on them in this
        # process (set by ``writes``), so evicting the entry means rebuilding it for the next one.
        self.pinned: Callable[[UUID], bool] = lambda _flow_id: False

    def get(self, flow_id: UUID) -> FlowEntry | None:
        entry = self._entries.get(flow_id)
        if entry is not None:
            self._entries.move_to_end(flow_id)
        return entry

    def put(self, entry: FlowEntry) -> None:
        """Add the entry; evict the least recently used entries over the limit, except pinned ones.

        So the cache can hold more than ``cache_max_flows`` entries while more flows than that
        have writers queued in this process; those entries are alive anyway (their writers hold
        them), and evicting them only made each next writer rebuild its graph.
        """
        self._entries[entry.flow_id] = entry
        self._entries.move_to_end(entry.flow_id)
        excess = len(self._entries) - config.cache_max_flows()
        if excess <= 0:
            return
        for flow_id in list(self._entries):  # oldest first
            if excess <= 0:
                break
            if flow_id == entry.flow_id or self.pinned(flow_id):
                continue
            del self._entries[flow_id]
            excess -= 1

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
        with bench.timed("load_db"):
            data = await oplog.read_flow_data(session, flow_id, as_bytes=True)
        if data is None:
            return None
        raw = data.data if data.data is not None else b'{"nodes":[],"edges":[]}'
        state = await call(config.engine().GraphState, raw, large=True, name="build")
    return FlowEntry(flow_id, state, data.current_revision)


async def catch_up(session: AsyncSession, entry: FlowEntry, head: int) -> None:
    """Replay the log rows after the entry's revision through ``head``. The caller holds ``entry.write``.

    Raises ``oplog.LogGapError`` when the rows are no longer there (compacted).
    """
    if entry.revision >= head:
        return
    t0 = time.perf_counter()
    with bench.timed("catchup_db"):
        rows = await oplog.rows_after(session, entry.flow_id, entry.revision, through=head)
    revisions = oplog.revisions_of(rows, entry.revision, through=head)
    await entry.replay([operation for _, operation in revisions], head)
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
