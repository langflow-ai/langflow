
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import select

from langflow.logging.logger import logger
from langflow.schema.data import Data
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow.utils import get_webhook_component_in_flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


FLOW_NOT_FOUND_ERROR_MSG = "Flow not found"

EXCLUDE_NODE_KEYS = {
    "selected",
    "dragging",
    "positionAbsolute",
    "measured",
    "resizing",
    "width",
    "height",
    "last_updated",
}

EXCLUDE_EDGE_KEYS = {
    "selected",
    "animated",
    "className",
    "style",
}


async def save_flow_checkpoint(
    *,
    session: AsyncSession | None = None,
    user_id: str | UUID | None = None,
    flow_id: str | UUID | None = None,
    update_data: dict | None = None
    ) -> None:
    """Save a flow in the Flow table and create a checkpoint in the FlowVersion table.

    This function updates the provided flow's
    Flow table row according to the update_data parameter.
    Checkpointing is solely determined by the "data" key,
    containing the graph data of the flow.
    If graph data is not present in update_data
    or does not differ from the current flow data,
    then checkpointing is skipped.
    If graph data is present in update_data
    and differs from the current flow's data,
    then the flow's latest version is incremented,
    and a new FlowVersion row is created
    with the latest version number and the new graph data,

    Args:
        session: The session to use for the database operations.
        If None, a new session will be created.
        user_id: The user ID of the user who the flow belongs to.
        flow_id: The flow ID of the flow to checkpoint.
        update_data: The flow to save in the checkpoint.

    Returns:
        The FlowVersion object if the checkpoint is saved successfully, otherwise None.
    """
    if not (user_id and flow_id):
        msg = "user_id and flow_id are required"
        raise ValueError(msg)
    if not update_data:
        logger.debug("Update data not provided, skipping checkpoint")
        return None
    print("WOW")
    uuid_user_id = _get_uuid(user_id)
    uuid_flow_id = _get_uuid(flow_id)

    if session:
        return await _save_flow_checkpoint(
            session=session,
            user_id=uuid_user_id,
            flow_id=uuid_flow_id,
            update_data=update_data,
            )

    async with session_scope() as session_:
        return await _save_flow_checkpoint(
            session=session_,
            user_id=uuid_user_id,
            flow_id=uuid_flow_id,
            update_data=update_data,
            )


async def _save_flow_checkpoint(
    session: AsyncSession,
    user_id: UUID,
    flow_id: UUID,
    update_data: dict,
) -> Flow | None:
    """Save a checkpoint of a flow."""
    print("OK")
    try:
        db_flow =  (
            await session.exec(
                select(Flow)
                .where(Flow.user_id == user_id)
                .where(Flow.id == flow_id)
                .with_for_update()
                )
            ).first()
    except Exception as e:
        msg = f"Failed to fetch flow {e}"
        raise ValueError(msg) from e

    if not db_flow:
        msg = f"Failed to checkpoint flow: {FLOW_NOT_FOUND_ERROR_MSG}"
        raise ValueError(msg)

    update_data.pop("latest_version", None) # prevent bad update to latest_version
    for key, val in update_data.items():
        setattr(db_flow, key, val)

    await configure_flow_webhook_and_folder(db_flow, session, user_id)
    db_flow.updated_at = datetime.now(timezone.utc)
    # create new checkpoint iff graph data changed
    if (
        "data" in update_data and
        normalized_flow_data(update_data["data"]) != normalized_flow_data(db_flow.data)
    ): # note that None and {} (empty dict) are acceptable values for flow data
        print("HAHA FLOW CHANGED")
        print("HAHA latest_version", db_flow.latest_version)
        db_flow.latest_version += 1
        print("HAHA latest_version + 1", db_flow.latest_version)
        # session.add(
        #     FlowVersion(
        #         user_id=user_id,
        #         flow_id=flow_id,
        #         version=db_flow.latest_version,
        #         created_at=datetime.now(timezone.utc),
        #         flow_data=update_data["data"],
        #         )
        #     )

    session.add(db_flow)
    return db_flow


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
        return [
            Data(data=dict(version._mapping)) # noqa: SLF001
            for version in flow_versions
            ]
    except Exception as e:
        msg = f"Error getting flow history: {e}"
        raise ValueError(msg) from e



async def restore_flow_checkpoint(
    *,
    user_id: str | None = None,
    flow_id: str | None = None,
    version_id: int | None = None,
    flow_data_current: dict | None = None,
    ):
    """Restore a checkpoint of the flow."""
    if not (user_id and flow_id):
        msg = "user_id and flow_id are required"
        raise ValueError(msg)
    pass  # noqa: PIE790


########################################################
# Helper functions for filtering flow data for version comparison
########################################################
def normalized_flow_data(flow_data: dict | None):
    """Filters a deepcopy of flow data to exclude transient state."""
    copy_flow_data = deepcopy(flow_data)
    if copy_flow_data:
        copy_flow_data.pop("viewport", None)
        copy_flow_data.pop("chatHistory", None)
        remove_keys_from_dicts(copy_flow_data["nodes"], EXCLUDE_NODE_KEYS)
        remove_keys_from_dicts(copy_flow_data["edges"], EXCLUDE_EDGE_KEYS)
    return copy_flow_data


def remove_keys_from_dicts(dictlist : list[dict], exclude_keys : set):
    """Remove a set of keys from each dictionary in a list in-place."""
    dictlist = [
        {k: v for (k, v) in d.items() if k not in exclude_keys}
        for d in dictlist
    ]


########################################################
# Other helper functions
########################################################
async def get_default_folder(session: AsyncSession, user_id: UUID):
    return (
        await session.exec(
            select(Folder)
            .where(Folder.user_id == user_id)
            .where(Folder.name == DEFAULT_FOLDER_NAME)
            )
        ).first()


async def configure_flow_webhook_and_folder(db_flow: Flow, session: AsyncSession, user_id: UUID):
    webhook_component = get_webhook_component_in_flow(db_flow.data)
    db_flow.webhook = webhook_component is not None
    if db_flow.folder_id is None:
        default_folder = await get_default_folder(session, user_id)
        db_flow.folder_id = default_folder.id if default_folder else None


def _get_uuid(value: str | UUID) -> UUID:
    return UUID(value) if isinstance(value, str) else value
