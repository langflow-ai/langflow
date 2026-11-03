"""The checkpoint task: ``Flow.data`` and a system checkpoint row every N revisions, off the write path.

Single-flight per flow across processes. It does not take the flow's write lock:

0. The task claims the flow's checkpoint with ``pg_try_advisory_xact_lock`` on its
   own key (``flow_checkpoint:`` and the flow id) in a short transaction it holds
   until its checkpoint is committed. When another process holds the claim, or the
   newest system checkpoint is already within a cadence of the revision that started
   the task, the task skips before it serializes anything (bench ``checkpoint_skip``).
   The conditional update in step 3 stays the correctness guard.
1. The graph text at revision R: the cached graph's coalesced serialization
   (``cache``, ``wal``), or ``Flow.data`` at its revision (``nocache``).
2. The checkpoint hash, SHA-256 of the exact text the row stores (worker
   thread, no engine call): of the cached graph's text (``FlowEntry.text_and_hash``:
   a snapshot under the entry's lock, ``to_json`` and the hash after it), or of
   ``Flow.data``'s bytes in ``nocache``.
3. One transaction: ``wal`` moves ``Flow.data`` to R only if R is newer than
   the stored revision; then a system checkpoint row at R, only when the log
   has rows, ``Flow.current_revision >= R`` and no checkpoint is there yet.
   So every system checkpoint (a compaction cut point) is at or before
   ``Flow.current_revision``, and a WAL read (``Flow.data`` + the rows after
   it) never meets a compacted gap except in a race, which it retries.
4. When more than the retention window plus the compaction step is retained,
   compaction runs (``compaction.compact``): the cut is chosen and checked
   without a lock, and only its deletes run under the advisory lock.

The cadence is ``flow_revision_checkpoint_cadence`` (default 100 revisions).
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from sqlalchemy import event
from sqlalchemy.orm import Session

from langflow.services.deps import get_settings_service, session_scope
from langflow.services.flow_multiplayer import bench, compaction, config, oplog
from langflow.services.flow_multiplayer.cache import CACHE, EntryGoneError, call, entry_at_head, text_hash

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

_MAX_TRACKED = 4096
_last: OrderedDict[UUID, int] = OrderedDict()
_running: set[UUID] = set()
_tasks: set[asyncio.Task] = set()


def note_checkpoint(flow_id: UUID, revision: int) -> None:
    previous = _last.get(flow_id)
    _last[flow_id] = revision if previous is None else max(previous, revision)
    _last.move_to_end(flow_id)
    while len(_last) > _MAX_TRACKED:
        _last.popitem(last=False)


_PENDING_KEY = "flow_multiplayer_checkpoint"


def request_after_commit(session: AsyncSession, flow_id: UUID, end: int) -> None:
    """Run ``after_write`` once ``session``'s transaction commits (legacy saves in modes cache and wal)."""
    pending = session.info.setdefault(_PENDING_KEY, {})
    pending[flow_id] = max(end, pending.get(flow_id, end))


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    pending = session.info.pop(_PENDING_KEY, None)
    if not pending:
        return
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    for flow_id, end in pending.items():
        after_write(flow_id, end)


@event.listens_for(Session, "after_rollback")
def _after_rollback(session: Session) -> None:
    session.info.pop(_PENDING_KEY, None)


def after_write(flow_id: UUID, end: int) -> None:
    """Start the checkpoint task when ``end`` is a cadence past the last checkpoint this process knows."""
    last = _last.get(flow_id)
    if last is not None and end - last < config.checkpoint_cadence():
        return
    if flow_id in _running:
        return
    _running.add(flow_id)
    task = bench.spawn(_run(flow_id, end))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _run(flow_id: UUID, end: int) -> None:
    try:
        await checkpoint_now(flow_id, end)
    except Exception as exc:  # noqa: BLE001 -- the next write past the cadence retries
        logger.warning("Flow checkpoint failed", flow_id=str(flow_id), error_type=type(exc).__name__)
    finally:
        _running.discard(flow_id)


def _skip(flow_id: UUID, end: int, reason: str, t0: float, **fields: object) -> None:
    bench.event(
        "checkpoint_skip",
        flow=str(flow_id),
        target=end,
        reason=reason,
        dur=(time.perf_counter() - t0) * 1000,
        **fields,
    )


async def checkpoint_now(flow_id: UUID, end: int) -> int | None:
    """Checkpoint the flow for the write that ended at ``end``, unless another process does or did.

    Returns the checkpoint's revision, or None when skipped.
    """
    started = time.time()
    t0 = time.perf_counter()
    async with session_scope() as claim:
        # Held until this block ends, after the checkpoint's own transaction has committed.
        if not await oplog.claim_checkpoint(claim, flow_id):
            # The holder checkpoints this crossing; this process tries again a cadence later.
            note_checkpoint(flow_id, end)
            _skip(flow_id, end, "claimed", t0)
            return None
        state = await oplog.checkpoint_state(claim, flow_id)
        if state is None:
            _skip(flow_id, end, "gone", t0)
            return None
        current, newest = state
        note_checkpoint(flow_id, newest or 0)
        if end - (newest or 0) < config.checkpoint_cadence():
            # Another process checkpointed this crossing already (a system checkpoint row
            # implies Flow.current_revision at or past it in WAL).
            _skip(flow_id, end, "checkpointed", t0, current_revision=current, last_checkpoint=newest)
            return None
        revision = await _write_checkpoint(flow_id, end, started, t0)
    if revision is not None:
        await _compact_if_due(flow_id)
    return revision


async def _write_checkpoint(flow_id: UUID, end: int, started: float, t0: float) -> int | None:
    """Serialize, hash and store the newest graph this process can serialize (the caller holds the claim)."""
    async with AsyncExitStack() as consumers:
        t_claim = time.perf_counter()
        mode = config.write_mode()
        ser_cpu, ser_here = 0.0, False
        raw: bytes | None = None
        entry = None
        entry_hash, entry_hash_cpu = "", 0.0
        if config.uses_cache():
            if CACHE.get(flow_id) is None:
                _skip(flow_id, end, "not_cached", t0)
                return None
            try:
                # Caught up to the log first: a legacy save appends rows without touching the cache.
                async with session_scope() as session:
                    entry = await entry_at_head(session, flow_id, await oplog.read_head(session, flow_id))
                if entry is None:
                    _skip(flow_id, end, "not_cached", t0)
                    return None
                # The engine CPU of the text is of this revision's serialization, whoever ran it (shared).
                revision, text, ser_cpu, ser_here, entry_hash, entry_hash_cpu = await consumers.enter_async_context(
                    entry.text_and_hash()
                )
            except EntryGoneError:
                _skip(flow_id, end, "not_cached", t0)
                return None
        else:
            async with session_scope() as session:
                data = await oplog.read_flow_data(session, flow_id, as_bytes=True)
            if data is None or data.data is None:
                _skip(flow_id, end, "gone", t0)
                return None
            revision, raw = data.current_revision, data.data
            text = raw.decode()
        t_ser = time.perf_counter()
        if revision <= _last.get(flow_id, -1):
            _skip(flow_id, end, "not_newer", t0, revision=revision)
            return None
        if entry is not None:
            hash_from, graph_hash, hash_cpu = "text", entry_hash, entry_hash_cpu
        else:
            # ``raw`` is the text the row stores (``text`` is its decoding).
            hash_from = "stored"
            graph_hash, hash_cpu = await call(bench.engine_call_cpu, text_hash, raw, large=True, name="hash")
        t_hash = time.perf_counter()
        async with session_scope() as session:
            moved = await oplog.checkpoint_flow(session, flow_id, text, revision=revision) if mode == "wal" else False
            inserted = await oplog.insert_checkpoint_row(
                session, flow_id, text, revision=revision, graph_hash=graph_hash
            )
            await session.commit()
        t_db = time.perf_counter()
        note_checkpoint(flow_id, revision)
        bench.event(
            "checkpoint",
            flow=str(flow_id),
            revision=revision,
            start=started,
            end=time.time(),
            dur=(t_db - t0) * 1000,
            claim=(t_claim - t0) * 1000,
            ser=(t_ser - t_claim) * 1000,
            hash=(t_hash - t_ser) * 1000,
            ser_cpu=ser_cpu,
            ser_by_checkpoint=ser_here,
            hash_cpu=hash_cpu,
            hash_from=hash_from,
            db=(t_db - t_hash) * 1000,
            flow_moved=moved,
            row_inserted=inserted,
            bytes=len(text),
        )
        return revision


async def _compact_if_due(flow_id: UUID) -> None:
    async with session_scope() as session:
        first, last = await oplog.retained_range(session, flow_id)
    window = get_settings_service().settings.flow_revision_retention_window
    if compaction.due(first, last, window=window, step=config.compaction_step()):
        await compaction.compact(flow_id, last=last, window=window)


async def wait_idle() -> None:
    """Wait for running checkpoint tasks (tests and shutdown)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


def reset_for_tests() -> None:
    _last.clear()
    _running.clear()
