from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from sqlalchemy.exc import NoResultFound
from sqlmodel import select

from langflow.helpers.utils import get_uuid, require_all_ids
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_history.model import FlowHistory
from langflow.services.database.models.flow_history.schema import (
    DATA_LEVEL_CHECKPOINT_KEYS,
    TOP_LEVEL_CHECKPOINT_KEYS,
    IDType,
)
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


########################################################
# querying
########################################################
# (constants to use for error messages upstream)
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
    require_all_ids(user_id=user_id, item_id=flow_id, item_type="flow")

    user_uuid = get_uuid(user_id)
    flow_uuid = get_uuid(flow_id)

    if session:
        return await _save_flow_checkpoint(
            session=session,
            user_id=user_uuid,
            flow_id=flow_uuid,
            update_data=update_data,
        )

    async with session_scope() as _session:
        return await _save_flow_checkpoint(
            session=_session,
            user_id=user_uuid,
            flow_id=flow_uuid,
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
            ).one()

        db_flow_graph: dict = db_flow.data or {} # existing graph data
        update_graph: dict = update_data.get("data") or {} # updated graph data

        old_data  = {k: db_flow_graph.get(k) for k in DATA_LEVEL_CHECKPOINT_KEYS} | {
            k: getattr(db_flow, k) for k in TOP_LEVEL_CHECKPOINT_KEYS
            }
        new_data = old_data | {
            k: update_graph.get(k) for k in update_graph.keys() & DATA_LEVEL_CHECKPOINT_KEYS
            } | {k: update_data.get(k) for k in update_data.keys() & TOP_LEVEL_CHECKPOINT_KEYS}

        session.add(
            FlowHistory(
                user_id=user_id,
                flow_id=flow_id,
                flow_data=new_data,
                )
            )

        await logger.adebug("Created new checkpoint for flow %s", flow_id)

        # let any other updates to the flow be saved
        for key, val in update_data.items():
            setattr(db_flow, key, val)

        db_flow.updated_at = datetime.now(timezone.utc)

        session.add(db_flow)
    except NoResultFound:
        raise
    except Exception as e:
        msg = f"Failed to fetch flow {e}"
        raise ValueError(msg) from e

    return db_flow


async def list_flow_history(
    *,
    user_id: IDType,
    flow_id: IDType,
    ) -> dict:
    """List the versions of the flow."""
    require_all_ids(user_id=user_id, item_id=flow_id, item_type="flow")

    user_uuid = get_uuid(user_id)
    flow_uuid = get_uuid(flow_id)

    try:
        async with session_scope() as session:
            flow_history = (
                await session.exec(
                    select(FlowHistory.id, FlowHistory.created_at)
                    .where(FlowHistory.user_id == user_uuid)
                    .where(FlowHistory.flow_id == flow_uuid)
                    .order_by(FlowHistory.created_at.desc())
                    )
                ).all()

        return {
            "flow_id": flow_uuid,
            "flow_history": [
                dict(checkpoint._mapping) # noqa: SLF001
                for checkpoint in flow_history
                ],
            }
    except Exception as e:
        msg = f"Error getting flow history: {e}"
        raise ValueError(msg) from e


async def get_flow_checkpoint(
    *,
    user_id: IDType,
    version_id: IDType,
) -> FlowHistory:
    require_all_ids(user_id=user_id, item_id=version_id, item_type="version")

    user_uuid = get_uuid(user_id)
    version_uuid = get_uuid(version_id)

    try:
        async with session_scope() as session:
            db_flow = (
                await session.exec(
                    select(FlowHistory)
                    .where(FlowHistory.user_id == user_uuid)
                    .where(FlowHistory.id == version_uuid)
                    )
                ).one()
    except NoResultFound:
        raise
    except Exception as e:
        msg = f"Failed to fetch flow version: {e!s}"
        raise ValueError(msg) from e

    return db_flow


async def delete_flow_checkpoint(
    *,
    user_id: IDType,
    version_id: IDType,
) -> UUID:
    require_all_ids(user_id=user_id, item_id=version_id, item_type="version")

    user_uuid = get_uuid(user_id)
    version_uuid = get_uuid(version_id)

    try:
        async with session_scope() as session:
            db_flow = (
                await session.exec(
                    select(FlowHistory)
                    .where(FlowHistory.user_id == user_uuid)
                    .where(FlowHistory.id == version_uuid)
                    )
                ).one()
            await session.delete(db_flow)
    except NoResultFound:
        raise
    except Exception as e:
        msg = f"Failed to fetch flow version: {e!s}"
        raise ValueError(msg) from e

    return db_flow.id # return the version id
