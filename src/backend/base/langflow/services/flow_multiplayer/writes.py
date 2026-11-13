"""``POST /api/v2/flows/{id}/ops``: apply one operation batch to the flow's head and record it.

Every mode runs the same steps in one transaction:

1. ``pg_advisory_xact_lock`` on the flow (``oplog.lock_flow``).
2. One statement: the head revision from the log, whether the history has
   started, and the stored batch of this ``request_id`` (GIN lookup).
   A stored batch answers ``already_applied`` (same body hash) or 409
   ``REQUEST_ID_REUSED`` (another body).
3. The graph at the head: built from ``Flow.data`` (``nocache``), or the
   cached graph caught up from the log rows after its revision.
4. The batch applied with every rule (``stage`` on a cached graph).
5. ``cache``: the staged graph serialized (``to_json(staged=True)``).
6. The log rows appended. ``nocache`` and ``cache`` also write ``Flow.data``
   and its revision; ``wal`` does not touch the flow row.
7. Commit; then ``keep``. Any failure before that drops the staged batch.

After the commit, a checkpoint task runs when the cadence is reached.

Before step 1, the writer passes the flow's gate in this process
(``config.writers_per_flow``, default 1): only that many writers of one flow
open a session at a time, so the writers queued on a flow wait without a
database connection, and the pool stays free for other flows, reads and the
readiness probe. A writer lets the next one in when it starts its commit, so
the next writer is already queued on the advisory lock when the lock is
released. The advisory lock still orders writers across processes.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import orjson

from langflow.services.deps import get_settings_service, session_scope
from langflow.services.flow_multiplayer import bench, checkpoint, config, oplog
from langflow.services.flow_multiplayer.cache import (
    CACHE,
    EntryGoneError,
    FlowEntry,
    call,
    catch_up,
    text_hash,
    uncancellable,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

EMPTY_GRAPH = '{"nodes":[],"edges":[]}'
MAX_ATTEMPTS = 3


@dataclass
class OpsRequest:
    request_id: str
    base_revision: int | None
    operations_json: bytes
    count: int


class OpsRefusedError(Exception):
    """A refusal the client can act on: an HTTP status and a detail with a ``code``."""

    def __init__(self, status: int, detail: dict[str, Any]) -> None:
        super().__init__(detail.get("code"))
        self.status = status
        self.detail = detail


def _answer(status: str, head: int, start: int, end: int) -> dict[str, Any]:
    return {"status": status, "revision": head, "start_revision": start, "end_revision": end}


def _refusal(error: Exception, head: int) -> OpsRefusedError:
    details = dict(getattr(error, "details", None) or {})
    details.setdefault("code", getattr(error, "code", "FLOW_OPERATION_ERROR"))
    details.setdefault("message", str(error))
    details.setdefault("violations", [])
    details["latest_revision"] = head
    return OpsRefusedError(422, details)


class _Gate:
    __slots__ = ("semaphore", "users")

    def __init__(self, size: int) -> None:
        self.semaphore = asyncio.Semaphore(size)
        self.users = 0


_gates: dict[UUID, _Gate] = {}


def _writers_queued(flow_id: UUID) -> bool:
    """Writers wait at the flow's gate behind the one inside: keep its cached graph."""
    gate = _gates.get(flow_id)
    return gate is not None and gate.users > 1


CACHE.pinned = _writers_queued


class _Permit:
    """A writer's place in its flow's gate; ``release`` lets the next writer in before this one ends."""

    __slots__ = ("held", "semaphore")

    def __init__(self, semaphore: asyncio.Semaphore | None) -> None:
        self.semaphore = semaphore
        self.held = False

    async def acquire(self) -> None:
        if self.semaphore is not None and not self.held:
            with bench.timed("gate"):
                await self.semaphore.acquire()
            self.held = True

    def release(self) -> None:
        if self.semaphore is not None and self.held:
            self.held = False
            self.semaphore.release()


_permit: ContextVar[_Permit | None] = ContextVar("flow_ops_gate_permit", default=None)


def _let_next_writer_in() -> None:
    """Give the flow's gate to the next writer; called just before the commit.

    The next writer takes its connection and queues on the advisory lock while this commit runs,
    so the lock passes to it at the commit with no event-loop turn in between. A waiting writer
    holds a connection only for the length of this commit.
    """
    permit = _permit.get()
    if permit is not None:
        permit.release()


@contextlib.asynccontextmanager
async def flow_gate(flow_id: UUID) -> AsyncIterator[_Permit]:
    """Admit at most ``config.writers_per_flow()`` writers of the flow at a time; the rest wait here.

    Waiting here holds no database connection. Bench step ``gate``: the wait. A writer gives its
    place to the next one when it starts its commit (``_let_next_writer_in``).
    """
    size = config.writers_per_flow()
    if size == 0:
        yield _Permit(None)
        return
    gate = _gates.get(flow_id)
    if gate is None:
        gate = _gates[flow_id] = _Gate(size)
    gate.users += 1
    permit = _Permit(gate.semaphore)
    token = _permit.set(permit)
    try:
        await permit.acquire()
        yield permit
    finally:
        permit.release()
        _permit.reset(token)
        gate.users -= 1
        if gate.users == 0 and _gates.get(flow_id) is gate:
            del _gates[flow_id]


async def apply_ops(
    flow_id: UUID,
    actor_id: UUID,
    request: OpsRequest,
    *,
    authorize: Callable[[AsyncSession], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """Apply the batch; ``authorize`` runs first in the write's transaction (the permission check)."""
    operations_sha256 = oplog.body_hash(request.operations_json)
    async with flow_gate(flow_id) as permit:
        for attempt in range(MAX_ATTEMPTS):
            await permit.acquire()  # again on a retry after the place was given up
            try:
                return await _write(flow_id, actor_id, request, operations_sha256, authorize)
            except (oplog.LogGapError, EntryGoneError):
                # The cached graph's rows were compacted, or a failed commit evicted it: rebuild.
                CACHE.evict(flow_id)
                if attempt == MAX_ATTEMPTS - 1:
                    raise
    msg = "unreachable"
    raise AssertionError(msg)


async def _write(
    flow_id: UUID,
    actor_id: UUID,
    request: OpsRequest,
    operations_sha256: str,
    authorize: Callable[[AsyncSession], Awaitable[None]] | None,
) -> dict[str, Any]:
    mode = config.write_mode()
    async with session_scope() as session:
        answer, end = await _in_session(session, flow_id, actor_id, request, operations_sha256, authorize, mode)
        closing = time.perf_counter()
    # Leaving the session returns its connection to the pool.
    bench.add("close", (time.perf_counter() - closing) * 1000)
    if end is not None:
        checkpoint.after_write(flow_id, end)
    return answer


async def _in_session(
    session: AsyncSession,
    flow_id: UUID,
    actor_id: UUID,
    request: OpsRequest,
    operations_sha256: str,
    authorize: Callable[[AsyncSession], Awaitable[None]] | None,
    mode: str,
) -> tuple[dict[str, Any], int | None]:
    if authorize is not None:
        await authorize(session)
    with bench.timed("lock"):
        await oplog.lock_flow(session, flow_id)
    with bench.timed("head"):
        read = await oplog.read_head_and_retry(session, flow_id, request.request_id)
    if not read.exists:
        raise OpsRefusedError(404, {"code": "FLOW_NOT_FOUND", "message": "Flow not found"})
    head = read.head
    match = oplog.find_retry(read.retry_rows, request.request_id)
    if match is not None:
        if match.body_sha256 != operations_sha256:
            raise OpsRefusedError(
                409,
                {
                    "code": "REQUEST_ID_REUSED",
                    "message": "This request_id was already used for another batch.",
                    "latest_revision": head,
                },
            )
        bench.put("result", "already_applied")
        return _answer("already_applied", head, match.start_revision, match.end_revision), None
    if request.base_revision is not None and request.base_revision > head:
        raise OpsRefusedError(
            409,
            {
                "code": "BASE_REVISION_AHEAD",
                "message": "base_revision is newer than the flow's latest revision.",
                "latest_revision": head,
            },
        )

    started = (head > 0 or read.has_anchor) and not read.paused
    if not started:
        head = await _start_history(session, flow_id, read)

    if mode == "nocache":
        answer, end = await _write_nocache(session, flow_id, actor_id, request, operations_sha256, head)
    else:
        answer, end = await _write_cached(session, flow_id, actor_id, request, operations_sha256, head, mode=mode)
    return answer, end


async def _start_history(session: AsyncSession, flow_id: UUID, read: oplog.HeadRead) -> int:
    """Write the checkpoint the flow's history starts from: revision 0, or one past a paused history."""
    data = await oplog.read_flow_data(session, flow_id, as_bytes=True)
    raw = (data.data if data is not None else None) or EMPTY_GRAPH.encode()
    text = raw.decode()
    revision = max(read.head, read.latest) + 1 if read.paused else 0
    # The checkpoint stores ``raw`` as it is, so its hash is of those bytes.
    graph_hash = await call(text_hash, raw, large=True, name="hash")
    await oplog.start_history(
        session,
        flow_id,
        data.user_id if data is not None else None,
        text,
        revision=revision,
        graph_hash=graph_hash,
        move_flow=read.paused,
    )
    if read.paused:
        CACHE.evict(flow_id)
    checkpoint.note_checkpoint(flow_id, revision)
    return revision


def _rows(forward: list[bytes], head: int) -> list[tuple[int, int, list[bytes]]]:
    settings = get_settings_service().settings
    return oplog.pack_rows(
        forward,
        first_revision=head + 1,
        ops_limit=settings.flow_op_log_row_ops_limit,
        bytes_limit=settings.flow_op_log_row_bytes_limit,
    )


async def _append(
    session: AsyncSession,
    flow_id: UUID,
    forward: list[bytes],
    head: int,
    *,
    request: OpsRequest,
    actor_id: UUID,
    operations_sha256: str,
) -> int:
    rows = _rows(forward, head)
    with bench.timed("append"):
        await oplog.append_rows(
            session,
            flow_id,
            rows,
            request_id=request.request_id,
            actor_id=actor_id,
            operations_sha256=operations_sha256,
        )
    return rows[-1][1]


async def _commit(session: AsyncSession) -> None:
    _let_next_writer_in()
    with bench.timed("commit"):
        await session.commit()


async def _write_nocache(
    session: AsyncSession,
    flow_id: UUID,
    actor_id: UUID,
    request: OpsRequest,
    operations_sha256: str,
    head: int,
) -> tuple[dict[str, Any], int | None]:
    engine = config.engine()
    with bench.timed("load"):
        with bench.timed("load_db"):
            data = await oplog.read_flow_data(session, flow_id, as_bytes=True)
        raw = (data.data if data is not None else None) or EMPTY_GRAPH.encode()
        state = await call(engine.GraphState, raw, large=True, name="build")
    if data is not None and data.current_revision < head:
        # Flow.data is behind the log (written in another mode): replay the rows after it.
        t0 = time.perf_counter()
        with bench.timed("catchup_db"):
            rows = await oplog.rows_after(session, flow_id, data.current_revision, through=head)
        revisions = oplog.revisions_of(rows, data.current_revision, through=head)
        payload = orjson.dumps([operation for _, operation in revisions])
        await call(state.replay, payload, large=True, name="replay")
        bench.add("catchup", (time.perf_counter() - t0) * 1000)
        bench.add("catchup_n", len(revisions))
    try:
        with bench.timed("stage"):
            # A new graph: the first batch checks the whole graph, so it is a large call.
            result = await call(state.apply, request.operations_json, forward_json=True, large=True, name="stage")
    except engine.EngineError as error:
        raise _refusal(error, head) from None
    forward = result.get("forward_operations_json") or []
    if not forward:
        await _commit(session)
        return _answer("applied", head, head + 1, head), None
    end = await _append(
        session, flow_id, forward, head, request=request, actor_id=actor_id, operations_sha256=operations_sha256
    )
    with bench.timed("ser"):
        new_text = await call(state.to_json, large=True, name="to_json")
    with bench.timed("flow_write"):
        await oplog.write_flow(session, flow_id, new_text, revision=end, actor_id=actor_id, token=uuid.uuid4())
    await _commit(session)
    bench.put("result", "applied")
    return _answer("applied", end, head + 1, end), end


async def _write_cached(
    session: AsyncSession,
    flow_id: UUID,
    actor_id: UUID,
    request: OpsRequest,
    operations_sha256: str,
    head: int,
    *,
    mode: str,
) -> tuple[dict[str, Any], int | None]:
    entry = await CACHE.load(session, flow_id)
    if entry is None:
        raise OpsRefusedError(404, {"code": "FLOW_NOT_FOUND", "message": "Flow not found"})
    async with entry.write:
        if entry.revision > head:
            # Only after a database reset or a lost commit outcome: the cache is not the log.
            CACHE.evict(flow_id, entry)
            raise EntryGoneError
        try:
            await catch_up(session, entry, head)
        except BaseException:
            CACHE.evict(flow_id, entry)
            raise
        text: str | None = None
        end: int | None = None
        try:
            with bench.timed("stage"):
                # Inline, except the first batch on a newly built graph: the engine checks the whole graph then.
                async with entry.use:
                    forward = await call(entry.state.stage_json, request.operations_json, large=entry.new, name="stage")
            entry.new = False
            if forward:
                if mode == "cache":
                    with bench.timed("ser"):
                        async with entry.use:
                            text = await call(entry.state.to_json, staged=True, large=True, name="to_json_staged")
                end = await _append(
                    session,
                    flow_id,
                    forward,
                    head,
                    request=request,
                    actor_id=actor_id,
                    operations_sha256=operations_sha256,
                )
                if text is not None:
                    with bench.timed("flow_write"):
                        await oplog.write_flow(
                            session, flow_id, text, revision=end, actor_id=actor_id, token=uuid.uuid4()
                        )
            await _commit(session)
        except config.engine().EngineError as error:
            # Refused by the engine: a refused batch changes nothing and stays unstaged.
            raise _refusal(error, head) from None
        except BaseException:
            await _discard(flow_id, entry)
            raise
        try:
            # Committed: keep the batch and move the revision even when this request is cancelled
            # meanwhile, so the entry never holds a committed batch staged under its old revision.
            await uncancellable(_keep(entry, end))
        except BaseException:
            CACHE.evict(flow_id, entry)
            raise
    bench.put("result", "applied")
    if end is None:
        return _answer("applied", head, head + 1, head), None
    return _answer("applied", end, head + 1, end), end


async def _keep(entry: FlowEntry, end: int | None = None) -> None:
    """Keep the staged batch and move the entry to ``end`` in one step, under ``entry.use``.

    A keep that fails drops the batch in the same step, so the graph stays at the entry's revision.
    """
    with bench.timed("keep"):
        async with entry.use:
            try:
                bench.engine_call("keep", entry.state.keep)
            except BaseException:
                if entry.state.staged:
                    entry.state.drop()
                raise
            if end is not None:
                entry.revision = end
                entry.invalidate_serialized()


async def _discard(flow_id: UUID, entry: FlowEntry) -> None:
    """After any failure but an engine refusal: evict the entry, and drop a batch it still has staged.

    Evicting first means no new request gets the entry; the next one rebuilds it from the database.
    """
    CACHE.evict(flow_id, entry)
    async with entry.use:
        if entry.state.staged:
            bench.engine_call("drop", entry.state.drop)
