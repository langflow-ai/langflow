"""Reconstructing a flow's graph at any recorded revision.

Replay starts from the newest checkpoint at or before the revision and applies
recorded operations forward, one revision at a time, so every revision is
reachable, including one in the middle of a row. It requires every revision to
appear exactly once and in order; anything else is corruption, reported with
the flow, revision and kind of damage and never silently papered over with the
nearest state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.services.flow_operations import FlowOperationError, dump_flow_operation
from sqlalchemy import Text, cast
from sqlmodel import func, select

from langflow.services.database.models.flow_operation import FlowOperation
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.flow_history.envelope import decode_row
from langflow.services.flow_history.errors import (
    FlowHistoryCorruptionError,
    FlowRevisionNotFoundError,
    FlowRevisionNotRetainedError,
)
from langflow.services.flow_history.store import latest_anchor_at_or_before, rows_covering

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


async def reconstruct_graph(
    session: AsyncSession,
    flow_id: UUID,
    revision: int,
    *,
    latest_revision: int,
    verify_anchor: bool = False,
) -> dict[str, Any]:
    """Return the flow's graph at ``revision``.

    The result may share nested values with a stored checkpoint; deep-copy it
    before storing or mutating it. ``verify_anchor`` also checks the starting
    checkpoint's hash, for readers that hand the graph to someone; a write
    compares the result with the stored flow anyway, which catches the same damage.
    """
    if revision < 0 or revision > latest_revision:
        msg = f"Flow {flow_id} has no revision {revision}"
        raise FlowRevisionNotFoundError(msg)

    # Reads take no lock, so a read that races compaction can pick a checkpoint
    # whose rows compaction then deletes, and see a gap. Compaction only ever
    # leaves a consistent state behind, so another read settles it; real damage
    # fails every attempt.
    attempts = 3
    for attempt in range(attempts):
        try:
            return await _reconstruct(session, flow_id, revision, latest_revision, verify_anchor=verify_anchor)
        except FlowHistoryCorruptionError:
            if attempt == attempts - 1:
                raise
    msg = "unreachable"
    raise AssertionError(msg)


async def retention_cutoff(session: AsyncSession, flow_id: UUID, latest_revision: int) -> int:
    """Return the first revision the history can still replay to.

    It is where the first retained row ends, where compaction always leaves a
    checkpoint. With no rows left (after a purge) only the latest revision is.
    """
    earliest_end = (
        await session.exec(select(func.min(FlowOperation.end_revision)).where(FlowOperation.flow_id == flow_id))
    ).one()
    return earliest_end if earliest_end is not None else latest_revision


async def _reconstruct(
    session: AsyncSession, flow_id: UUID, revision: int, latest_revision: int, *, verify_anchor: bool
) -> dict[str, Any]:
    anchor = await latest_anchor_at_or_before(session, flow_id, revision)
    if anchor is not None and anchor.operation_revision == revision:
        if verify_anchor:
            await verify_checkpoint(session, anchor)
        return anchor.data
    try:
        if anchor is None:
            raise FlowHistoryCorruptionError(flow_id, "no checkpoint to replay from", revision=revision)
        if verify_anchor:
            await verify_checkpoint(session, anchor)
        return await replay_from(session, flow_id, anchor, revision)
    except FlowHistoryCorruptionError:
        # Below the cutoff, missing history was compacted away on purpose.
        if revision < await retention_cutoff(session, flow_id, latest_revision):
            msg = f"Revision {revision} of flow {flow_id} is no longer retained"
            raise FlowRevisionNotRetainedError(msg) from None
        raise


async def verify_checkpoint(session: AsyncSession, checkpoint: FlowVersion) -> None:
    """Raise when a checkpoint's stored text no longer hashes to its stored hash (worker thread: a whole graph)."""
    from langflow.services.flow_multiplayer.cache import call, text_hash

    statement = select(cast(FlowVersion.data, Text)).where(FlowVersion.id == checkpoint.id)
    stored = (await session.exec(statement)).first()
    if stored is None or await call(text_hash, stored, large=True, name="hash") != checkpoint.graph_hash:
        raise FlowHistoryCorruptionError(
            checkpoint.flow_id, "checkpoint does not match its hash", revision=checkpoint.operation_revision
        )


async def replay_from(session: AsyncSession, flow_id: UUID, anchor: FlowVersion, revision: int) -> dict[str, Any]:
    """Apply the recorded operations after ``anchor`` up to and including ``revision``."""
    anchor_revision = anchor.operation_revision or 0
    # Each apply reads and builds the whole graph: a worker thread, as for the multiplayer path.
    from langflow.services.flow_multiplayer.cache import whole_flow

    graph: dict[str, Any] = anchor.data
    expected = anchor_revision + 1
    for row in await rows_covering(session, flow_id, after=anchor_revision, through=revision):
        for recorded in decode_row(row):
            if recorded.revision <= anchor_revision:
                # The row began before the checkpoint.
                continue
            if recorded.revision > revision:
                break
            if recorded.revision != expected:
                raise FlowHistoryCorruptionError(flow_id, "missing revisions", revision=expected)
            try:
                graph = (await whole_flow("apply", graph, [dump_flow_operation(recorded.operation)], forward=False))[
                    "flow_data"
                ]
            except FlowOperationError as exc:
                raise FlowHistoryCorruptionError(flow_id, "operation does not apply", revision=expected) from exc
            expected += 1
    if expected != revision + 1:
        raise FlowHistoryCorruptionError(flow_id, "missing revisions", revision=expected)
    return graph
