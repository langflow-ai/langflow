"""Reading a flow's history as a timeline.

The timeline has one entry per history row, newest first, because a row is the
unit preview and restore work in: an entry's end revision is a point the flow
can be viewed at or returned to. Each entry names its authors and the saved
versions that belong to its revisions; operations are included only on
request, stripped of secrets, for the entry's description and for playback.
Revision numbers are the page cursor: ``before`` is exclusive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from lfx.services.flow_operations import dump_flow_operation
from sqlmodel import col, func, select

from langflow.services.database.models.flow_operation import FlowOperation
from langflow.services.database.models.flow_version.crud import SAVED_VERSION
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.flow_history.envelope import RecordedOperation, decode_row
from langflow.services.flow_history.secrets import strip_operation_secrets

if TYPE_CHECKING:
    from collections.abc import Collection
    from datetime import datetime
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.flow.model import Flow


@dataclass
class TimelineOperation:
    revision: int
    actor_user_id: UUID
    request_id: UUID
    operation: dict[str, Any]
    cause: str | None = None


@dataclass
class TimelineEntry:
    id: UUID
    start_revision: int
    end_revision: int
    created_at: datetime | None
    actor_user_ids: list[UUID]
    request_ids: list[UUID]
    versions: list[FlowVersion] = field(default_factory=list)
    operations: list[TimelineOperation] | None = None


@dataclass
class TimelinePage:
    entries: list[TimelineEntry]
    next_before: int | None
    earliest_revision: int | None


async def read_timeline(
    session: AsyncSession,
    flow: Flow,
    *,
    before: int | None,
    limit: int,
    include_operations: bool,
    known_variable_names: Collection[str],
) -> TimelinePage:
    """Return one page of the flow's timeline, newest entry first."""
    statement = select(FlowOperation).where(FlowOperation.flow_id == flow.id)
    if before is not None:
        statement = statement.where(col(FlowOperation.start_revision) < before)
    statement = statement.order_by(col(FlowOperation.start_revision).desc()).limit(limit + 1)
    rows = list((await session.exec(statement)).all())
    has_more = len(rows) > limit
    rows = rows[:limit]

    entries = []
    for row in rows:
        recorded = decode_row(row)
        entry = TimelineEntry(
            id=row.id,
            start_revision=row.start_revision,
            end_revision=row.end_revision,
            created_at=row.created_at,
            actor_user_ids=list(dict.fromkeys(operation.actor_user_id for operation in recorded)),
            request_ids=list(dict.fromkeys(operation.request_id for operation in recorded)),
        )
        if include_operations:
            entry.operations = [_timeline_operation(operation, known_variable_names) for operation in recorded]
        entries.append(entry)

    await _pin_versions(session, flow, entries)
    earliest = (
        await session.exec(select(func.min(FlowOperation.start_revision)).where(FlowOperation.flow_id == flow.id))
    ).one()
    return TimelinePage(
        entries=entries,
        next_before=rows[-1].start_revision if has_more and rows else None,
        earliest_revision=earliest,
    )


def _timeline_operation(recorded: RecordedOperation, known_variable_names: Collection[str]) -> TimelineOperation:
    return TimelineOperation(
        revision=recorded.revision,
        actor_user_id=recorded.actor_user_id,
        request_id=recorded.request_id,
        operation=strip_operation_secrets(dump_flow_operation(recorded.operation), known_variable_names),
        cause=recorded.cause,
    )


async def _pin_versions(session: AsyncSession, flow: Flow, entries: list[TimelineEntry]) -> None:
    """Attach each saved version to the entry whose revisions contain it."""
    if not entries:
        return
    low = min(entry.start_revision for entry in entries)
    high = max(entry.end_revision for entry in entries)
    versions = (
        await session.exec(
            select(FlowVersion)
            .where(
                FlowVersion.flow_id == flow.id,
                SAVED_VERSION,
                col(FlowVersion.operation_revision) >= low,
                col(FlowVersion.operation_revision) <= high,
            )
            .order_by(col(FlowVersion.operation_revision), col(FlowVersion.version_number))
        )
    ).all()
    for version in versions:
        for entry in entries:
            if entry.start_revision <= version.operation_revision <= entry.end_revision:
                entry.versions.append(version)
                break
