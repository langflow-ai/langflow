from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from lfx.log import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, delete, func, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.flow_history.model import FlowHistory, FlowStateEnum
from langflow.services.deps import get_settings_service

MAX_VERSION_RETRIES = 3


async def get_next_version_number(session: AsyncSession, flow_id: UUID) -> int:
    result = await session.exec(select(func.max(FlowHistory.version_number)).where(FlowHistory.flow_id == flow_id))
    current_max = result.one()
    return (current_max or 0) + 1


async def create_flow_history_entry(
    session: AsyncSession,
    flow_id: UUID,
    user_id: UUID,
    data: dict | None,
    description: str | None = None,
    state: FlowStateEnum = FlowStateEnum.DRAFT,
) -> FlowHistory:
    """Create a history entry with retry on version number collision."""
    entry: FlowHistory | None = None
    for attempt in range(MAX_VERSION_RETRIES):
        version_number = await get_next_version_number(session, flow_id)
        entry = FlowHistory(
            flow_id=flow_id,
            user_id=user_id,
            data=data,
            description=description,
            state=state,
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
                raise
            await logger.awarning(
                "Version number collision for flow %s (attempt %d/%d), retrying",
                flow_id,
                attempt + 1,
                MAX_VERSION_RETRIES,
            )
            entry = None
            continue

    if entry is None:
        msg = f"Failed to create history entry for flow {flow_id} after {MAX_VERSION_RETRIES} retries"
        raise RuntimeError(msg)

    # Prune oldest entries beyond the configured limit, but never delete PUBLISHED entries
    max_entries = get_settings_service().settings.max_flow_history_entries_per_flow
    delete_older = delete(FlowHistory).where(
        FlowHistory.flow_id == flow_id,
        FlowHistory.state != FlowStateEnum.PUBLISHED,
        col(FlowHistory.id).in_(
            select(FlowHistory.id)
            .where(
                FlowHistory.flow_id == flow_id,
                FlowHistory.state != FlowStateEnum.PUBLISHED,
            )
            .order_by(col(FlowHistory.version_number).desc())
            .offset(max_entries)
        ),
    )
    result = await session.exec(delete_older)
    if hasattr(result, "rowcount") and result.rowcount:  # type: ignore[union-attr]
        await logger.adebug("Pruned %d old history entries for flow %s", result.rowcount, flow_id)  # type: ignore[union-attr]

    return entry


async def get_flow_history_list(
    session: AsyncSession,
    flow_id: UUID,
    user_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[FlowHistory]:
    result = await session.exec(
        select(FlowHistory)
        .where(FlowHistory.flow_id == flow_id, FlowHistory.user_id == user_id)
        .order_by(col(FlowHistory.version_number).desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.all())


async def get_flow_history_entry(
    session: AsyncSession,
    history_id: UUID,
    user_id: UUID,
) -> FlowHistory | None:
    result = await session.exec(select(FlowHistory).where(FlowHistory.id == history_id, FlowHistory.user_id == user_id))
    return result.first()


async def delete_flow_history_entry(
    session: AsyncSession,
    history_id: UUID,
    user_id: UUID,
    active_version_id: UUID | None,
) -> None:
    if active_version_id and history_id == active_version_id:
        raise HTTPException(status_code=400, detail="Cannot delete the active version")

    entry = await get_flow_history_entry(session, history_id, user_id)
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found")

    await session.delete(entry)
    await session.flush()


async def archive_previously_published(
    session: AsyncSession,
    flow_id: UUID,
    exclude_id: UUID,
) -> None:
    """Set all PUBLISHED entries to ARCHIVED (except exclude_id) using a single UPDATE."""
    stmt = (
        update(FlowHistory)
        .where(
            FlowHistory.flow_id == flow_id,
            FlowHistory.state == FlowStateEnum.PUBLISHED,
            FlowHistory.id != exclude_id,
        )
        .values(state=FlowStateEnum.ARCHIVED)
    )
    await session.exec(stmt)


async def set_entry_state(
    session: AsyncSession,
    history_id: UUID,
    state: FlowStateEnum,
) -> None:
    """Set the state of a single history entry using a targeted UPDATE."""
    stmt = (
        update(FlowHistory)
        .where(FlowHistory.id == history_id)
        .values(state=state)
    )
    result = await session.exec(stmt)
    if hasattr(result, "rowcount") and result.rowcount == 0:  # type: ignore[union-attr]
        await logger.awarning(
            "set_entry_state affected 0 rows for history_id=%s state=%s (possible race condition)",
            history_id,
            state,
        )
