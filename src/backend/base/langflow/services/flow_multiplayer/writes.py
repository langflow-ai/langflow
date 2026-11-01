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
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import orjson

from langflow.services.deps import get_settings_service, session_scope
from langflow.services.flow_multiplayer import bench, checkpoint, config, oplog
from langflow.services.flow_multiplayer.cache import CACHE, EntryGoneError, FlowEntry, call, catch_up

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
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


async def apply_ops(
    flow_id: UUID,
    actor_id: UUID,
    request: OpsRequest,
    *,
    authorize: Callable[[AsyncSession], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """Apply the batch; ``authorize`` runs first in the write's transaction (the permission check)."""
    operations_sha256 = oplog.body_hash(request.operations_json)
    for attempt in range(MAX_ATTEMPTS):
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
            return _answer("already_applied", head, match.start_revision, match.end_revision)
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
    if end is not None:
        checkpoint.after_write(flow_id, end)
    return answer


async def _start_history(session: AsyncSession, flow_id: UUID, read: oplog.HeadRead) -> int:
    """Write the checkpoint the flow's history starts from: revision 0, or one past a paused history."""
    data = await oplog.read_flow_data(session, flow_id)
    text = (data.data if data is not None else None) or EMPTY_GRAPH
    revision = max(read.head, read.latest) + 1 if read.paused else 0
    engine = config.engine()
    graph_hash = await call(lambda: engine.GraphPlain(text.encode()).graph_hash(), large=True)
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


def _rows(forward: list[Any], head: int) -> list[tuple[int, int, list[bytes]]]:
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
    forward: list[Any],
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
        data = await oplog.read_flow_data(session, flow_id)
        text = (data.data if data is not None else None) or EMPTY_GRAPH
        state = await call(engine.GraphState, text.encode(), large=True)
    if data is not None and data.current_revision < head:
        # Flow.data is behind the log (written in another mode): replay the rows after it.
        t0 = time.perf_counter()
        rows = await oplog.rows_after(session, flow_id, data.current_revision, through=head)
        revisions = oplog.revisions_of(rows, data.current_revision, through=head)
        await call(state.replay, orjson.dumps([operation for _, operation in revisions]), large=True)
        bench.add("catchup", (time.perf_counter() - t0) * 1000)
        bench.add("catchup_n", len(revisions))
    try:
        with bench.timed("stage"):
            # A new graph: the first batch checks the whole graph, so it is a large call.
            result = await call(state.apply, request.operations_json, forward=True, large=True)
    except engine.EngineError as error:
        raise _refusal(error, head) from None
    forward = result.get("forward_operations") or []
    if not forward:
        await _commit(session)
        return _answer("applied", head, head + 1, head), None
    end = await _append(
        session, flow_id, forward, head, request=request, actor_id=actor_id, operations_sha256=operations_sha256
    )
    with bench.timed("ser"):
        new_text = await call(state.to_json, large=True)
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
        await catch_up(session, entry, head)
        try:
            with bench.timed("stage"):
                # Inline, except the first batch on a newly built graph: the engine checks the whole graph then.
                async with entry.use:
                    result = await call(entry.state.stage, request.operations_json, forward=True, large=entry.new)
        except config.engine().EngineError as error:
            raise _refusal(error, head) from None
        entry.new = False
        text: str | None = None
        try:
            forward = result.get("forward_operations") or []
            if not forward:
                await _commit(session)
                await _keep(entry)
                return _answer("applied", head, head + 1, head), None
            if mode == "cache":
                with bench.timed("ser"):
                    async with entry.use:
                        text = await call(entry.state.to_json, staged=True, large=True)
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
                    await oplog.write_flow(session, flow_id, text, revision=end, actor_id=actor_id, token=uuid.uuid4())
            await _commit(session)
        except BaseException:
            await _drop(entry)
            raise
        await _keep(entry, end, text)
    bench.put("result", "applied")
    return _answer("applied", end, head + 1, end), end


async def _keep(entry: FlowEntry, end: int | None = None, text: str | None = None) -> None:
    with bench.timed("keep"):
        async with entry.use:
            entry.state.keep()
            if end is not None:
                entry.revision = end
                # Mode cache serialized this revision for Flow.data: readers share it.
                entry.json = (end, text) if text is not None else None


async def _drop(entry: FlowEntry) -> None:
    async with entry.use:
        entry.state.drop()
