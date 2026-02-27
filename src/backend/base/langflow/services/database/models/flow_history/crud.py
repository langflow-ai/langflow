from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log import logger
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import col, delete, func, select

from langflow.services.database.models.flow_history.exceptions import (
    FlowHistoryDataTooLargeError,
    FlowHistoryNotFoundError,
    FlowHistorySerializationError,
    FlowHistoryVersionConflictError,
)
from langflow.services.database.models.flow_history.model import FlowHistory
from langflow.services.database.models.flow_history_deployment_attachment.model import (
    FlowHistoryDeploymentAttachment,
)
from langflow.services.deps import get_settings_service

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

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
    """Create a history entry with retry on version number collision.

    NOTE: This function does NOT verify that user_id owns the flow.
    Callers are responsible for checking ownership before calling this.
    """
    if data is not None:
        import orjson

        try:
            data_size = len(orjson.dumps(data))
        except (TypeError, orjson.JSONEncodeError) as exc:
            msg = "Flow data could not be serialized. The data may contain non-serializable values."
            raise FlowHistorySerializationError(msg) from exc
        max_size = get_settings_service().settings.max_flow_history_data_size_bytes
        if data_size > max_size:
            raise FlowHistoryDataTooLargeError(data_size, max_size)

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
                raise FlowHistoryVersionConflictError(msg) from exc
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
        raise FlowHistoryVersionConflictError(msg)

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
    except SQLAlchemyError:
        await logger.awarning(
            "Failed to prune old history entries for flow %s — history table may exceed configured limit",
            flow_id,
            exc_info=True,
        )

    return entry


async def get_flow_history_list(
    session: AsyncSession,
    flow_id: UUID,
    user_id: UUID,
    limit: int = 50,
    offset: int = 0,
    deployment_ids: list[UUID] | None = None,
) -> list[FlowHistory]:
    stmt = select(FlowHistory).where(FlowHistory.flow_id == flow_id, FlowHistory.user_id == user_id)
    if deployment_ids:
        stmt = (
            stmt.join(
                FlowHistoryDeploymentAttachment,
                FlowHistoryDeploymentAttachment.history_id == FlowHistory.id,
            )
            .where(
                FlowHistoryDeploymentAttachment.user_id == user_id,
                FlowHistoryDeploymentAttachment.deployment_id.in_(deployment_ids),
            )
            .distinct()
        )
    result = await session.exec(stmt.order_by(col(FlowHistory.version_number).desc()).offset(offset).limit(limit))
    return list(result.all())


async def get_flow_history_counts_by_deployment_ids(
    session: AsyncSession,
    flow_id: UUID,
    user_id: UUID,
    deployment_ids: list[UUID],
) -> dict[UUID, int]:
    if not deployment_ids:
        return {}

    stmt = (
        select(
            FlowHistoryDeploymentAttachment.deployment_id,
            func.count(func.distinct(FlowHistoryDeploymentAttachment.history_id)),
        )
        .join(
            FlowHistory,
            FlowHistory.id == FlowHistoryDeploymentAttachment.history_id,
        )
        .where(
            FlowHistory.flow_id == flow_id,
            FlowHistory.user_id == user_id,
            FlowHistoryDeploymentAttachment.user_id == user_id,
            FlowHistoryDeploymentAttachment.deployment_id.in_(deployment_ids),
        )
        .group_by(FlowHistoryDeploymentAttachment.deployment_id)
    )
    rows = (await session.exec(stmt)).all()
    return {deployment_id: int(count) for deployment_id, count in rows}


async def get_flow_history_entry(
    session: AsyncSession,
    history_id: UUID,
    user_id: UUID,
) -> FlowHistory | None:
    result = await session.exec(select(FlowHistory).where(FlowHistory.id == history_id, FlowHistory.user_id == user_id))
    return result.first()


async def get_flow_history_entry_or_raise(
    session: AsyncSession,
    history_id: UUID,
    user_id: UUID,
    flow_id: UUID | None = None,
) -> FlowHistory:
    """Get a history entry or raise FlowHistoryNotFoundError.

    If flow_id is provided, also verifies the entry belongs to that flow.
    """
    entry = await get_flow_history_entry(session, history_id, user_id)
    if not entry or (flow_id is not None and entry.flow_id != flow_id):
        msg = f"History entry {history_id} not found"
        raise FlowHistoryNotFoundError(msg)
    return entry


async def delete_flow_history_entry(
    session: AsyncSession,
    history_id: UUID,
    user_id: UUID,
) -> None:
    entry = await get_flow_history_entry(session, history_id, user_id)
    if not entry:
        msg = f"History entry {history_id} not found"
        raise FlowHistoryNotFoundError(msg)

    await session.delete(entry)
    await session.flush()
