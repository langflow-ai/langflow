from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_history.model import FlowHistory
from langflow.services.database.models.flow_history.schema import CHECKPOINT_KEYS, IDType
from langflow.services.database.models.flow_history.utils import (
    _get_uuid,
    require_user_and_flow_ids,
    require_user_version_ids,
)
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession



########################################################
# querying
########################################################
# (constants to use for matching error messages upstream)
FLOW_NOT_FOUND_ERROR_MSG = "Flow not found."
FLOW_HISTORY_CHECKPOINT_NOT_FOUND_ERROR_MSG = "Flow history checkpoint not found."

async def save_flow_checkpoint(
    *,
    session: AsyncSession | None = None,
    user_id: IDType,
    flow_id: IDType,
    update_data: dict,
) -> Flow | None:
    """Save a flow in the Flow table and create a checkpoint in the FlowHistory table.

    This function updates the provided flow's
    Flow table row according to the update_data parameter.
    Checkpointing is determined by comparing the current flow data with the update data.
    If they differ, a new FlowHistory row is created.

    Args:
        session: The session to use for the database operations.
        If None, a new session will be created.
        user_id: The user ID of the user who the flow belongs to.
        flow_id: The flow ID of the flow to checkpoint.
        update_data: The updated flow data to save.

    Returns:
        Flow | None: The updated flow if successful, otherwise None.
    """
    require_user_and_flow_ids(user_id, flow_id)

    uuid_user_id = _get_uuid(user_id)
    uuid_flow_id = _get_uuid(flow_id)

    if session:
        return await _save_flow_checkpoint(
            session=session,
            user_id=uuid_user_id,
            flow_id=uuid_flow_id,
            update_data=update_data,
        )

    async with session_scope() as _session:
        return await _save_flow_checkpoint(
            session=_session,
            user_id=uuid_user_id,
            flow_id=uuid_flow_id,
            update_data=update_data,
        )


async def _save_flow_checkpoint(
    session: AsyncSession,
    user_id: UUID,
    flow_id: UUID,
    update_data: dict,
) -> Flow:
    """Save a checkpoint of a flow."""
    try:
        db_flow = (
            await session.exec(
                select(Flow)
                .where(Flow.user_id == user_id)
                .where(Flow.id == flow_id)
                # .with_for_update()
            )
        ).first()
    except Exception as e:
        msg = f"Failed to fetch flow {e}"
        raise ValueError(msg) from e

    if not db_flow:
        msg = f"Failed to checkpoint flow: {FLOW_NOT_FOUND_ERROR_MSG}"
        raise ValueError(msg)

    old_flow_data  = {k: getattr(db_flow, k) for k in CHECKPOINT_KEYS}
    new_flow_data = old_flow_data | {k: v for k, v in update_data.items() if k in CHECKPOINT_KEYS}
    if old_flow_data != new_flow_data:
        session.add(
            FlowHistory(
                user_id=user_id,
                flow_id=flow_id,
                flow_data=new_flow_data,
                )
            )
        logger.debug("Created new checkpoint for flow %s", flow_id)

    # let any other updates to the flow be saved
    for key, val in update_data.items():
        setattr(db_flow, key, val)

    db_flow.updated_at = datetime.now(timezone.utc)
    session.add(db_flow)

    return db_flow


async def list_flow_history(
    *,
    user_id: IDType,
    flow_id: IDType,
) -> list[dict] | None:
    """List the versions of the flow."""
    require_user_and_flow_ids(user_id, flow_id)

    uuid_user_id = _get_uuid(user_id)
    uuid_flow_id = _get_uuid(flow_id)

    try:
        async with session_scope() as session:
            flow_history = (
                await session.exec(
                    select(FlowHistory.id, FlowHistory.created_at)
                    .where(FlowHistory.user_id == uuid_user_id)
                    .where(FlowHistory.flow_id == uuid_flow_id)
                )
            ).all()
        return {
            "flow_id": uuid_user_id,
            "flow_history": [checkpoint._mapping for checkpoint in flow_history],  # noqa: SLF001
        }
    except Exception as e:
        msg = f"Error getting flow history: {e}"
        raise ValueError(msg) from e


async def get_flow_checkpoint(
    *,
    user_id: IDType,
    version_id: IDType,
) -> FlowHistory:
    require_user_version_ids(user_id, version_id)

    user_uuid = _get_uuid(user_id)
    version_uuid = _get_uuid(version_id)

    try:
        async with session_scope() as session:
            db_flow = (
                await session.exec(
                    select(FlowHistory)
                    .where(FlowHistory.user_id == user_uuid)
                    .where(FlowHistory.id == version_uuid)
                )
            ).one()
    except Exception as e:
        msg = f"Failed to fetch flow version: {e!s}"
        raise ValueError(msg) from e

    if not db_flow:
        raise ValueError(FLOW_HISTORY_CHECKPOINT_NOT_FOUND_ERROR_MSG)

    return db_flow
