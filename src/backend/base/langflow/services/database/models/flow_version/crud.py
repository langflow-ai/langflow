from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log import logger
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import col, delete, func, select

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.flow_version.exceptions import (
    FlowVersionConflictError,
    FlowVersionNotFoundError,
)
from langflow.services.database.models.flow_version.model import (
    FlowVersion,
)
from langflow.services.deps import get_settings_service

MAX_VERSION_RETRIES = 3


async def get_next_version_number(session: AsyncSession, flow_id: UUID) -> int:
    result = await session.exec(select(func.max(FlowVersion.version_number)).where(FlowVersion.flow_id == flow_id))
    current_max = result.one()
    return (current_max or 0) + 1


async def create_flow_version_entry(
    session: AsyncSession,
    flow_id: UUID,
    user_id: UUID,
    data: dict | None,
    description: str | None = None,
) -> FlowVersion:
    """Create a version entry with retry on version number collision.

    NOTE: This function does NOT verify that user_id owns the flow.
    Callers are responsible for checking ownership before calling this.
    """
    entry: FlowVersion | None = None
    for attempt in range(MAX_VERSION_RETRIES):
        version_number = await get_next_version_number(session, flow_id)
        entry = FlowVersion(
            flow_id=flow_id,
            user_id=user_id,
            data=data,
            description=description,
            version_number=version_number,
        )
        try:
            async with session.begin_nested():
                session.add(entry)
                await session.flush()
            break
        except IntegrityError as exc:
            if "unique_flow_version_number" not in str(exc).lower():
                raise  # Not a version collision — don't retry
            if attempt == MAX_VERSION_RETRIES - 1:
                msg = (
                    f"Failed to create version entry for flow {flow_id} after "
                    f"{MAX_VERSION_RETRIES} retries due to version number conflicts"
                )
                raise FlowVersionConflictError(msg) from exc
            await logger.awarning(
                "Version number collision for flow %s (attempt %d/%d), retrying",
                flow_id,
                attempt + 1,
                MAX_VERSION_RETRIES,
            )
            entry = None
            continue

    if entry is None:
        msg = (
            f"Failed to create version entry for flow {flow_id} after "
            f"{MAX_VERSION_RETRIES} retries due to version number conflicts"
        )
        raise FlowVersionConflictError(msg)

    # Prune oldest entries beyond the configured limit.
    # NOTE: Concurrent snapshot requests for the same flow could both insert
    # before either prunes, temporarily exceeding the limit by one or more
    # entries. This is acceptable — the excess self-corrects on the next
    # snapshot, and serializing with SELECT FOR UPDATE would add contention
    # for a non-critical constraint.
    try:
        max_entries = get_settings_service().settings.max_flow_version_entries_per_flow
        delete_older = delete(FlowVersion).where(
            FlowVersion.flow_id == flow_id,
            col(FlowVersion.id).in_(
                select(FlowVersion.id)
                .where(FlowVersion.flow_id == flow_id)
                .order_by(col(FlowVersion.version_number).desc())
                .offset(max_entries)
            ),
        )
        result = await session.exec(delete_older)
        if hasattr(result, "rowcount") and result.rowcount:  # type: ignore[union-attr]
            await logger.adebug("Pruned %d old version entries for flow %s", result.rowcount, flow_id)  # type: ignore[union-attr]
    except SQLAlchemyError:
        # Pruning is best-effort: we don't fail the snapshot because pruning broke.
        # Logged at error level because repeated failures cause unbounded table growth
        # and may need operational attention.
        await logger.aerror(
            "Failed to prune old version entries for flow %s — version table may exceed configured limit",
            flow_id,
            exc_info=True,
        )

    return entry


async def get_flow_version_list(
    session: AsyncSession,
    flow_id: UUID,
    user_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[FlowVersion]:
    result = await session.exec(
        select(FlowVersion)
        .where(FlowVersion.flow_id == flow_id, FlowVersion.user_id == user_id)
        .order_by(col(FlowVersion.version_number).desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.all())


async def get_flow_version_entry(
    session: AsyncSession,
    version_id: UUID,
    user_id: UUID,
) -> FlowVersion | None:
    result = await session.exec(select(FlowVersion).where(FlowVersion.id == version_id, FlowVersion.user_id == user_id))
    return result.first()


async def get_flow_version_entry_or_raise(
    session: AsyncSession,
    version_id: UUID,
    user_id: UUID,
    flow_id: UUID | None = None,
) -> FlowVersion:
    """Get a version entry or raise FlowVersionNotFoundError.

    If flow_id is provided, also verifies the entry belongs to that flow.
    """
    entry = await get_flow_version_entry(session, version_id, user_id)
    if not entry or (flow_id is not None and entry.flow_id != flow_id):
        msg = f"Version entry {version_id} not found"
        raise FlowVersionNotFoundError(msg)
    return entry


async def delete_flow_version_entry(
    session: AsyncSession,
    version_id: UUID,
    user_id: UUID,
) -> None:
    entry = await get_flow_version_entry(session, version_id, user_id)
    if not entry:
        msg = f"Version entry {version_id} not found"
        raise FlowVersionNotFoundError(msg)

    await session.delete(entry)
    await session.flush()
