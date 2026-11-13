"""Compaction of a multiplayer flow's history, with the flow's advisory lock held only for the log rows' delete.

The checkpoint task calls ``compact`` once more than the retention window
plus the compaction step (``config.compaction_step``) is retained, so it runs
once every step, not at every checkpoint. It cuts at the newest system
checkpoint ``k`` that ends a row ``s..k`` and leaves at least the window after
it, as the legacy maintenance does (``maintenance.compact_to``): the row
``s..k`` stays, every row ending before ``s`` goes, and so do the system
checkpoints before ``k`` that are not retained.

1. Without a lock: one statement picks the cut, a second reads that one
   checkpoint's text, and its SHA-256 is checked against the stored hash in a worker thread.
   This needs no lock: a checkpoint row never changes, and when it is deleted
   meanwhile the guarded delete of step 2 deletes nothing.
2. One short transaction, the only work under the lock: the advisory lock,
   the log rows' delete, the commit. The rows go only while the cut's row and
   its checkpoint are both still there; after a concurrent purge or
   compaction nothing is deleted.
3. Only when log rows went: a second transaction, without the lock, deletes
   the system checkpoints before the cut (large rows, so slow to delete).
   Nothing reads them any more: a read below the first retained revision is
   "not retained", and replay starts at the cut or after it.

PostgreSQL only, like every multiplayer statement.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text

from langflow.services.deps import session_scope
from langflow.services.flow_multiplayer import bench, oplog
from langflow.services.flow_multiplayer.cache import call, text_hash

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

# The newest system checkpoint that ends a row, is at or before :newest, and is past the first retained row's end.
# No graph here: PostgreSQL computes the select list before the sort, so it would read every candidate's graph.
CUT = text(
    """
    SELECT v.id, v.operation_revision, v.graph_hash, o.start_revision
      FROM flow_version v
      JOIN flow_operation o ON o.flow_id = v.flow_id AND o.end_revision = v.operation_revision
      JOIN flow f ON f.id = v.flow_id
     WHERE v.flow_id = :flow_id AND f.user_id IS NOT NULL
       AND v.version_number IS NULL AND v.graph_hash IS NOT NULL
       AND v.operation_revision <= :newest
       AND v.operation_revision > (SELECT min(end_revision) FROM flow_operation WHERE flow_id = :flow_id)
     ORDER BY v.operation_revision DESC
     LIMIT 1
    """
)
# The cut's graph, for that one row only.
CUT_DATA = text("SELECT data::text FROM flow_version WHERE id = :checkpoint_id")
# The rows before the cut's row, only while that row and the checkpoint are still there.
DELETE_ROWS = text(
    """
    DELETE FROM flow_operation
     WHERE flow_id = :flow_id AND end_revision < :first_kept
       AND EXISTS (SELECT 1 FROM flow_operation
                    WHERE flow_id = :flow_id AND end_revision = :cut AND start_revision = :first_kept)
       AND EXISTS (SELECT 1 FROM flow_version WHERE id = :checkpoint_id AND flow_id = :flow_id)
    """
)
# A retained checkpoint stays as a snapshot, like a saved version.
DELETE_CHECKPOINTS = text(
    """
    DELETE FROM flow_version
     WHERE flow_id = :flow_id AND version_number IS NULL AND operation_revision < :cut AND retained = false
    """
)


@dataclass
class Cut:
    checkpoint_id: UUID
    revision: int
    graph_hash: str
    first_kept: int


def due(first: int | None, last: int | None, *, window: int, step: int) -> bool:
    """Whether more than the window plus the step is retained."""
    return first is not None and last is not None and last - first + 1 > window + step


async def compact(flow_id: UUID, *, last: int, window: int) -> int | None:
    """Compact the history to the newest cut that keeps ``window`` revisions; return the cut, or None.

    ``last`` is the head the caller read. Records a ``compaction`` bench event with the time of every
    phase, ``lock_held`` (from the lock granted to the commit's end) and ``checkpoints_delete``.
    """
    started = time.time()
    t0 = time.perf_counter()
    async with session_scope() as session:
        row = (await session.execute(CUT, {"flow_id": flow_id, "newest": last - window})).first()
        cut = None if row is None else Cut(row[0], int(row[1]), row[2], int(row[3]))
        data = None
        if cut is not None:
            data = (await session.execute(CUT_DATA, {"checkpoint_id": cut.checkpoint_id})).scalar_one_or_none()
    t_plan = time.perf_counter()
    if cut is None or data is None:
        # No cut, or its checkpoint was deleted meanwhile (a concurrent compaction or purge).
        bench.event("compaction", flow=str(flow_id), cutoff=None, start=started, dur=(t_plan - t0) * 1000)
        return None
    verify_cpu = await _verify(flow_id, cut, data)
    del data
    t_verify = time.perf_counter()
    async with session_scope() as session:
        await oplog.lock_flow(session, flow_id)
        t_lock = time.perf_counter()
        rows_deleted = await delete_rows(session, flow_id, cut)
        t_delete = time.perf_counter()
        await session.commit()
        t_commit = time.perf_counter()
    checkpoints_deleted = 0
    if rows_deleted:
        async with session_scope() as session:
            checkpoints_deleted = await delete_checkpoints(session, flow_id, cut)
            await session.commit()
    t_checkpoints = time.perf_counter()
    bench.event(
        "compaction",
        flow=str(flow_id),
        cutoff=cut.revision if rows_deleted else None,
        start=started,
        end=time.time(),
        dur=(t_checkpoints - t0) * 1000,
        plan=(t_plan - t0) * 1000,
        verify=(t_verify - t_plan) * 1000,
        verify_cpu=verify_cpu,
        lock=(t_lock - t_verify) * 1000,
        delete=(t_delete - t_lock) * 1000,
        commit=(t_commit - t_delete) * 1000,
        lock_held=(t_commit - t_lock) * 1000,
        checkpoints_delete=(t_checkpoints - t_commit) * 1000,
        rows_deleted=rows_deleted,
        checkpoints_deleted=checkpoints_deleted,
    )
    return cut.revision if rows_deleted else None


async def _verify(flow_id: UUID, cut: Cut, data: str) -> float:
    """Raise when the checkpoint's stored text no longer hashes to its stored hash; return the hash CPU in ms.

    It becomes the only anchor for everything after it, so its stored bytes must be unchanged.
    The hash is SHA-256 of the text (worker thread, no engine call).
    """
    from langflow.services.flow_history.errors import FlowHistoryCorruptionError

    graph_hash, cpu = await call(bench.engine_call_cpu, text_hash, data, large=True, name="verify")
    if graph_hash != cut.graph_hash:
        raise FlowHistoryCorruptionError(flow_id, "checkpoint does not match its hash", revision=cut.revision)
    return cpu


async def delete_rows(session: AsyncSession, flow_id: UUID, cut: Cut) -> int:
    """Delete the log rows before the cut's row; the caller holds the flow's advisory lock. Returns the rows deleted.

    Deletes nothing when the cut's row or its checkpoint is gone: a concurrent purge or compaction came first.
    """
    from langflow.services.database.models.flow_operation.append_only import delete_history_rows

    params = {
        "flow_id": flow_id,
        "first_kept": cut.first_kept,
        "cut": cut.revision,
        "checkpoint_id": cut.checkpoint_id,
    }
    return await delete_history_rows(session, DELETE_ROWS.bindparams(**params))


async def delete_checkpoints(session: AsyncSession, flow_id: UUID, cut: Cut) -> int:
    """Delete the system checkpoints before the cut that are not retained, once its rows are gone (no lock)."""
    result = await session.exec(DELETE_CHECKPOINTS.bindparams(flow_id=flow_id, cut=cut.revision))
    return result.rowcount
