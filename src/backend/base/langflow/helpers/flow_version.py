
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, select, update

from langflow.schema.data import Data
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


async def save_flow_checkpoint(
    *,
    session: AsyncSession | None = None,
    user_id: str | UUID | None = None,
    flow_id: str | UUID | None = None,
    flow: Flow | None = None,
    flush_session: bool = False,
    ) -> FlowVersion | None:
    """Save a checkpoint of a flow by creating a new FlowVersion row.

    Args:
        session: The session to use for the database operations.
        If None, a new session will be created.
        user_id: The user ID of the user who is saving the checkpoint.
        flow_id: The flow ID of the flow to checkpoint.
        flow: The flow object to save in the checkpoint.
        flush_session: Whether to flush the session after the operations.

    Returns:
        The FlowVersion object if the checkpoint is saved successfully, otherwise None.
    """
    if not (user_id and flow_id and flow):
        msg = "user_id, flow_id and flow_data are required"
        raise ValueError(msg)

    uuid_user_id = _get_uuid(user_id)
    uuid_flow_id = _get_uuid(flow_id)

    if session is not None:
        return await _save_flow_checkpoint(
            session,
            uuid_user_id,
            uuid_flow_id,
            flow,
            flush_session,
            )

    async with session_scope() as scoped_session:
        return await _save_flow_checkpoint(
            scoped_session,
            uuid_user_id,
            uuid_flow_id,
            flow,
            flush_session,
            )


async def _save_flow_checkpoint(
    db: AsyncSession,
    user_id: UUID,
    flow_id: UUID,
    flow: Flow,
    flush_session: bool = False, # noqa: FBT001, FBT002
) -> FlowVersion | None:
    """Save a checkpoint of a flow."""
    try:
        next_version = (
            await db.exec(
                update(Flow)
                .where(Flow.id == flow_id)
                .where(Flow.user_id == user_id)
                .values(latest_version=func.coalesce(Flow.latest_version, 0) + 1)
                .returning(Flow.latest_version)
                )
            ).scalar_one()
    except Exception as e:
        msg = f"Error getting next version: {e}"
        raise ValueError(msg) from e

    version_row = FlowVersion(
        flow_id=flow_id,
        user_id=user_id,
        version=next_version,
        created_at=datetime.now(timezone.utc),
        flow_data=flow.data,
        flow_name=flow.name,
        flow_description=flow.description,
    )

    db.add(version_row)

    if flush_session:
        await db.flush()

    return version_row


async def list_flow_versions(
    *,
    user_id: str | UUID | None = None,
    flow_id: str | UUID | None = None,
    ) -> list[Data]:
    """List the versions of the flow."""
    if not (user_id and flow_id):
        msg = "user_id and flow_id are required"
        raise ValueError(msg)

    uuid_user_id = _get_uuid(user_id)
    uuid_flow_id = _get_uuid(flow_id)
    try:
        async with session_scope() as session:
            flow_versions = (
                await session.exec(
                    select(FlowVersion)
                    .where(FlowVersion.user_id == uuid_user_id)
                    .where(FlowVersion.flow_id == uuid_flow_id)
                    .order_by(FlowVersion.version.desc())
                    )
                ).all()
        return [Data(data=dict(version._mapping)) for version in flow_versions]  # noqa: SLF001
    except Exception as e:
        msg = f"Error getting flow history: {e}"
        raise ValueError(msg) from e



async def restore_flow_checkpoint(
    *,
    user_id: str | None = None,
    flow_id: str | None = None,
    version_id: str | None = None,
    flow_data_current: dict | None = None,
    ):
    """Restore a checkpoint of the flow."""
    pass  # noqa: PIE790


def _get_uuid(value: str | UUID) -> UUID:
    return UUID(value) if isinstance(value, str) else value
