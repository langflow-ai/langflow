
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, select, update

from langflow.logging.logger import logger
from langflow.schema.data import Data
from langflow.services.database.models.base import orjson_dumps
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio.session import AsyncSessionTransaction
    from sqlmodel.ext.asyncio.session import AsyncSession


async def save_flow_checkpoint(
    *,
    session: AsyncSession | None = None,
    user_id: str | UUID | None = None,
    flow_id: str | UUID | None = None,
    flow_data: dict | None = None,
    ) -> FlowVersion | None:
    """Save a checkpoint of a flow by creating a new FlowVersion row.

    This function does not update the
    provided flow's data in the Flow table.
    Instead, it updates the latest version number
    in the Flow table and adds a corresponding row
    in the FlowVersion table containing the new data.

    Args:
        session: The session to use for the database operations.
        If None, a new session will be created.
        user_id: The user ID of the user who the flow belongs to.
        flow_id: The flow ID of the flow to checkpoint.
        flow_data: The flow data to save in the checkpoint.

    Returns:
        The FlowVersion object if the checkpoint is saved successfully, otherwise None.
    """
    if not (user_id and flow_id):
        msg = "user_id and flow_id are required"
        raise ValueError(msg)
    if not flow_data:
        logger.debug("Flow data is empty, skipping checkpoint")
        return None

    uuid_user_id = _get_uuid(user_id)
    uuid_flow_id = _get_uuid(flow_id)

    transaction_scope = session.begin_nested if session else session_scope
    async with transaction_scope() as transaction:
        session_ = session or transaction
        return await _save_flow_checkpoint(
            session=session_,
            transaction=transaction,
            user_id=uuid_user_id,
            flow_id=uuid_flow_id,
            flow_data=flow_data,
            )


async def _save_flow_checkpoint(
    session: AsyncSession,
    transaction: AsyncSessionTransaction | AsyncSession,
    user_id: UUID,
    flow_id: UUID,
    flow_data: dict,
) -> FlowVersion | None:
    """Save a checkpoint of a flow."""
    try:
        # optimistic update of the latest version number
        next_version, old_flow_data = (
            await session.exec(
                update(Flow)
                .where(Flow.id == flow_id)
                .where(Flow.user_id == user_id)
                .values(latest_version=func.coalesce(Flow.latest_version, 0) + 1)
                .returning(Flow.latest_version, Flow.data)
                )
            ).one()
    except Exception as e:
        msg = f"Error getting next version: {e}"
        raise ValueError(msg) from e

    if compute_dict_hash(flow_data) == compute_dict_hash(old_flow_data):
        logger.warning("No changes detected in the flow, skipping checkpoint")
        return await transaction.rollback() # rollback the optimistic update

    version_row = FlowVersion(
        user_id=user_id,
        flow_id=flow_id,
        version=next_version,
        created_at=datetime.now(timezone.utc),
        flow_data=flow_data,
    )

    session.add(version_row)

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


def _get_uuid(value: str | UUID) -> UUID:
    return UUID(value) if isinstance(value, str) else value


########################################################
# Helper functions for filtering flow data for version comparison
########################################################
EXCLUDE_NODE_KEYS = {
    "selected",
    "dragging",
    "positionAbsolute",
    "measured",
    "resizing",
    "width",
    "height",
    "last_updated"
}

EXCLUDE_EDGE_KEYS = {
    "selected",
    "animated",
    "className",
    "style",
}


def filter_json(flow_data: dict):
    """Filters the flow data in-place to exclude transient UI state for version comparison."""
    flow_data.pop("viewport", None)
    flow_data.pop("chatHistory", None)

    remove_keys_from_dicts(flow_data["nodes"], EXCLUDE_NODE_KEYS)
    remove_keys_from_dicts(flow_data["edges"], EXCLUDE_EDGE_KEYS)


def remove_keys_from_dicts(dictlist : list[dict], exclude_keys : set):
    """Remove a set of keys from each dictionary in a list in-place."""
    dictlist = [
        {k: v for (k, v) in d if k not in exclude_keys}
        for d in dictlist
    ]


def compute_dict_hash(flow_data: dict):
    """Computes the hash of the flow data."""
    filter_json(flow_data_copy := flow_data.copy())
    cleaned_flow_json = orjson_dumps(flow_data_copy, sort_keys=True)
    return hashlib.sha256(cleaned_flow_json.encode("utf-8")).hexdigest()
