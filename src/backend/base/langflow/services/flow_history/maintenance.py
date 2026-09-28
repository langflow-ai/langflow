"""Automatic checkpoints and compaction of a flow's history.

Both run lazily, off the save path. A graph write that crosses a threshold asks
for maintenance of its flow; once the write's transaction commits, a
background task takes the flow's lock and does the work. The write never waits
for it, and a failed or lost task only delays the work until the next write
crosses the threshold again. The task re-derives everything under the lock, so
running it twice, or late, is harmless.

- **Checkpoint**: once ``flow_revision_checkpoint_cadence`` operations have
  been recorded since the newest checkpoint, the flow's stored graph becomes a
  new checkpoint at its current revision, so replay never walks far. It is
  taken from ``Flow.data`` and written only when that equals the replayed
  graph: hashing the replay instead would bake a tampered but applicable
  operation into an anchor and hide it for good.
- **Compaction**: once more than ``flow_revision_retention_window`` operations
  are retained, the history before the newest system checkpoint ``k`` that
  still keeps the window is deleted. ``k`` ends a row ``s..k``; that row stays,
  so the operations that produced ``k`` remain visible, and every row ending
  before ``s`` goes, together with the system checkpoints before ``k``. Saved
  versions are kept as snapshots. Rows are only ever deleted whole.

Afterwards the first retained revision is ``MIN(flow_operation.end_revision)``
and a checkpoint sits exactly there; reads below it are "not retained".

At most one task runs per flow: on PostgreSQL a transaction-scoped advisory
lock keyed on the flow lets a second worker exit at once; SQLite admits one
writer anyway, and an in-process guard skips duplicates.
"""

from __future__ import annotations

import asyncio
import zlib
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from sqlalchemy import event, text
from sqlalchemy.orm import Session
from sqlmodel import col, delete, func, select

from langflow.services.database.models.flow.guards import lock_flow_for_update
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_operation import FlowOperation
from langflow.services.database.models.flow_operation.append_only import delete_history_rows
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.flow_history.errors import FlowHistoryCorruptionError, FlowRevisionMismatchError
from langflow.services.flow_history.recorder import checkpoint_system, projection_matches
from langflow.services.flow_history.replay import verify_checkpoint
from langflow.services.flow_history.store import anchors_of, has_anchor

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

_PENDING_KEY = "flow_history_maintenance"
_ADVISORY_NAMESPACE = zlib.crc32(b"revision_compaction") - 2**31
_running: set[UUID] = set()
_tasks: set[asyncio.Task] = set()


def request_maintenance(session: AsyncSession, flow_id: UUID) -> None:
    """Ask for maintenance of ``flow_id`` once ``session``'s transaction commits."""
    session.info.setdefault(_PENDING_KEY, set()).add(flow_id)


@event.listens_for(Session, "after_commit")
def _schedule_after_commit(session: Session) -> None:
    flow_ids = session.info.pop(_PENDING_KEY, None)
    if not flow_ids:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    for flow_id in flow_ids:
        task = loop.create_task(run_maintenance(flow_id))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)


@event.listens_for(Session, "after_rollback")
def _discard_after_rollback(session: Session) -> None:
    session.info.pop(_PENDING_KEY, None)


async def needs_maintenance(session: AsyncSession, flow: Flow) -> bool:
    """Return whether a checkpoint is due or compaction has somewhere newer to cut to."""
    cadence = get_settings_service().settings.flow_revision_checkpoint_cadence
    newest = await _latest_system_checkpoint_revision(session, flow.id)
    if newest is not None and flow.latest_revision - newest >= cadence:
        return True
    return await _compaction_cutoff(session, flow) is not None


async def run_maintenance(flow_id: UUID) -> None:
    """Entry point for the task scheduled after a write commits."""
    await perform_maintenance(flow_id)


async def perform_maintenance(flow_id: UUID) -> None:
    """Checkpoint and compact one flow's history in its own transaction. Never raises."""
    if flow_id in _running:
        return
    _running.add(flow_id)
    try:
        async with session_scope() as session:
            if not await _try_advisory_lock(session, flow_id):
                return
            flow = await session.get(Flow, flow_id)
            if flow is None or flow.user_id is None:
                return
            await lock_flow_for_update(session, flow)
            await checkpoint_if_due(session, flow)
            await compact_if_due(session, flow)
    except Exception as exc:  # noqa: BLE001 -- maintenance is retried by the next write that needs it
        logger.warning(
            "Flow history maintenance failed",
            flow_id=str(flow_id),
            error_type=type(exc).__name__,
        )
    finally:
        _running.discard(flow_id)


async def checkpoint_if_due(session: AsyncSession, flow: Flow) -> FlowVersion | None:
    """Write a checkpoint of ``flow.data`` at its current revision when the cadence is reached."""
    # Counted from the newest system checkpoint, not any saved version: only
    # system checkpoints can become compaction cutoffs, since a saved version
    # can be deleted or pruned.
    cadence = get_settings_service().settings.flow_revision_checkpoint_cadence
    newest = await _latest_system_checkpoint_revision(session, flow.id)
    if newest is None or flow.current_revision - newest < cadence:
        return None
    return await write_checkpoint(session, flow)


async def write_checkpoint(session: AsyncSession, flow: Flow) -> FlowVersion | None:
    """Checkpoint ``flow.data`` at ``flow.current_revision``, if it is the recorded graph."""
    if not await projection_matches(session, flow):
        logger.warning(
            "Flow history checkpoint skipped: stored data does not match its revision",
            flow_id=str(flow.id),
            revision=flow.current_revision,
        )
        return None
    checkpoint = checkpoint_system(flow, flow.data, revision=flow.current_revision)
    session.add(checkpoint)
    await session.flush()
    return checkpoint


async def compact_if_due(session: AsyncSession, flow: Flow) -> int | None:
    """Compact the history when more than the retention window is retained; return the new cutoff."""
    cutoff = await _compaction_cutoff(session, flow)
    if cutoff is None:
        return None
    await compact_to(session, flow, cutoff)
    return cutoff.operation_revision


async def purge_history(session: AsyncSession, flow: Flow) -> None:
    """Delete every history row and older system checkpoint, keeping a checkpoint of ``flow.data``.

    The caller holds the flow's lock. A flow whose stored graph no longer
    matches its history cannot be purged until that is repaired, since the
    checkpoint left behind must be the recorded graph.
    """
    if flow.latest_revision == 0 and not await has_anchor(session, flow.id):
        return
    checkpoint = (
        await session.exec(
            anchors_of(flow.id).where(
                FlowVersion.operation_revision == flow.latest_revision,
                col(FlowVersion.version_number).is_(None),
            )
        )
    ).first()
    if checkpoint is None:
        checkpoint = await write_checkpoint(session, flow)
    if checkpoint is None:
        raise FlowRevisionMismatchError(
            flow.id, current_revision=flow.current_revision, latest_revision=flow.latest_revision
        )
    await compact_to(session, flow, checkpoint, keep_row=False)


async def _compaction_cutoff(session: AsyncSession, flow: Flow) -> FlowVersion | None:
    """Return the checkpoint to compact to, when more than the retention window is retained."""
    window = get_settings_service().settings.flow_revision_retention_window
    earliest = await _earliest_retained_start(session, flow.id)
    if earliest is None or flow.latest_revision - earliest + 1 <= window:
        return None
    return await _cutoff_checkpoint(session, flow, keep=window)


async def compact_to(session: AsyncSession, flow: Flow, checkpoint: FlowVersion, *, keep_row: bool = True) -> None:
    """Delete the history before ``checkpoint``, which must be a system checkpoint ending a row.

    With ``keep_row`` the row that ends at the checkpoint stays, so the
    operations that produced it remain in the timeline. Purge drops it too.
    """
    # It becomes the only anchor for everything after it, so it must still be intact.
    verify_checkpoint(checkpoint)
    revision = checkpoint.operation_revision
    ending_row = (
        await session.exec(
            select(FlowOperation).where(FlowOperation.flow_id == flow.id, FlowOperation.end_revision == revision)
        )
    ).first()
    if ending_row is None and revision != flow.latest_revision:
        raise FlowHistoryCorruptionError(flow.id, "checkpoint does not end a row", revision=revision)

    first_kept = ending_row.start_revision if (ending_row is not None and keep_row) else revision + 1
    await delete_history_rows(
        session,
        delete(FlowOperation).where(
            FlowOperation.flow_id == flow.id,
            col(FlowOperation.end_revision) < first_kept,
        ),
    )
    await session.exec(
        delete(FlowVersion).where(
            FlowVersion.flow_id == flow.id,
            col(FlowVersion.version_number).is_(None),
            col(FlowVersion.operation_revision) < revision,
        )
    )


async def _cutoff_checkpoint(session: AsyncSession, flow: Flow, *, keep: int) -> FlowVersion | None:
    """Pick the newest system checkpoint that ends a row and still leaves ``keep`` operations after it."""
    candidates = (
        await session.exec(
            select(FlowVersion)
            .join(
                FlowOperation,
                (FlowOperation.flow_id == FlowVersion.flow_id)
                & (FlowOperation.end_revision == FlowVersion.operation_revision),
            )
            .where(
                FlowVersion.flow_id == flow.id,
                col(FlowVersion.version_number).is_(None),
                col(FlowVersion.graph_hash).is_not(None),
                col(FlowVersion.operation_revision) <= flow.latest_revision - keep,
            )
            .order_by(col(FlowVersion.operation_revision).desc())
            .limit(1)
        )
    ).first()
    earliest = await _earliest_retained_end(session, flow.id)
    if candidates is None or earliest is None or candidates.operation_revision <= earliest:
        # Already compacted to this checkpoint, or nothing newer to compact to.
        return None
    return candidates


async def _latest_system_checkpoint_revision(session: AsyncSession, flow_id: UUID) -> int | None:
    return (
        await session.exec(
            select(func.max(FlowVersion.operation_revision)).where(
                FlowVersion.flow_id == flow_id,
                col(FlowVersion.version_number).is_(None),
                col(FlowVersion.graph_hash).is_not(None),
            )
        )
    ).one()


async def _earliest_retained_start(session: AsyncSession, flow_id: UUID) -> int | None:
    return (
        await session.exec(select(func.min(FlowOperation.start_revision)).where(FlowOperation.flow_id == flow_id))
    ).one()


async def _earliest_retained_end(session: AsyncSession, flow_id: UUID) -> int | None:
    return (
        await session.exec(select(func.min(FlowOperation.end_revision)).where(FlowOperation.flow_id == flow_id))
    ).one()


async def _try_advisory_lock(session: AsyncSession, flow_id: UUID) -> bool:
    if session.get_bind().dialect.name != "postgresql":
        return True
    key = zlib.crc32(flow_id.bytes) - 2**31
    acquired = await session.exec(
        text("SELECT pg_try_advisory_xact_lock(:namespace, :key)").bindparams(namespace=_ADVISORY_NAMESPACE, key=key)
    )
    return bool(acquired.scalar())
