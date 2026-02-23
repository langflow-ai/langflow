from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from lfx.log import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.flow_history.model import FlowHistory
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
) -> FlowHistory:
    """Create a history entry with retry on version number collision."""
    if data is not None:
        import orjson

        try:
            data_size = len(orjson.dumps(data))
        except (TypeError, orjson.JSONEncodeError) as exc:
            raise HTTPException(
                status_code=422,
                detail="Flow data could not be serialized. The data may contain non-serializable values.",
            ) from exc
        max_size = get_settings_service().settings.max_flow_history_data_size_bytes
        if data_size > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"Flow data size ({data_size:,} bytes) exceeds the maximum allowed "
                f"for history snapshots ({max_size:,} bytes)",
            )

    entry: FlowHistory | None = None
    for attempt in range(MAX_VERSION_RETRIES):
        version_number = await get_next_version_number(session, flow_id)
        entry = FlowHistory(
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
                    f"Failed to create history entry for flow {flow_id} after "
                    f"{MAX_VERSION_RETRIES} retries due to version number conflicts"
                )
                raise HTTPException(status_code=409, detail=msg) from exc
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
            f"Failed to create history entry for flow {flow_id} after "
            f"{MAX_VERSION_RETRIES} retries due to version number conflicts"
        )
        raise HTTPException(status_code=409, detail=msg)

    # Prune oldest entries beyond the configured limit.
    # NOTE: Concurrent snapshot requests for the same flow could both insert
    # before either prunes, temporarily exceeding the limit by one or more
    # entries. This is acceptable — the excess self-corrects on the next
    # snapshot, and serializing with SELECT FOR UPDATE would add contention
    # for a non-critical constraint.
    try:
        max_entries = get_settings_service().settings.max_flow_history_entries_per_flow
        delete_older = delete(FlowHistory).where(
            FlowHistory.flow_id == flow_id,
            col(FlowHistory.id).in_(
                select(FlowHistory.id)
                .where(FlowHistory.flow_id == flow_id)
                .order_by(col(FlowHistory.version_number).desc())
                .offset(max_entries)
            ),
        )
        result = await session.exec(delete_older)
        if hasattr(result, "rowcount") and result.rowcount:  # type: ignore[union-attr]
            await logger.adebug("Pruned %d old history entries for flow %s", result.rowcount, flow_id)  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        await logger.awarning("Failed to prune old history entries for flow %s", flow_id, exc_info=True)

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
) -> None:
    entry = await get_flow_history_entry(session, history_id, user_id)
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found")

    await session.delete(entry)
    await session.flush()
