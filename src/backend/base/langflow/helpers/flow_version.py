
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

    print('HAHAHA OLD HASH: ', compute_dict_hash(old_flow_data))
    print('HAHAHA NEW HASH: ', compute_dict_hash(flow_data))
    if compute_dict_hash(flow_data) == compute_dict_hash(old_flow_data):
        logger.warning("No changes detected in the flow, skipping checkpoint")
        return await transaction.rollback() # rollback the optimistic update

    compute_dict_hash(old_flow_data, "old")
    compute_dict_hash(flow_data, "new")

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
    version_id: str | None = None,
    flow_data_current: dict | None = None,
    ):
    """Restore a checkpoint of the flow."""
    pass  # noqa: PIE790


def _get_uuid(value: str | UUID) -> UUID:
    return UUID(value) if isinstance(value, str) else value


########################################################
# Helper functions for filtering flow data for version comparison
########################################################
exclude_node_keys = {
    "__top_level__": {
        "selected",
        "dragging",
        "positionAbsolute",
        "measured",
        "resizing",
        "width",
        "height",
        "last_updated",
        },
    "template": {
        # "is_refresh",
        # "_frontend_node_flow_id",
        # "_frontend_node_folder_id",
    },
    "__recursive__": {
        # "override_skip",
        # "track_in_telemetry",
        # "options",
        # "input_types",
        # "value",
    },
    "outputs": {
        # "loop_types",
        # "hidden",
        # "required_inputs",
    }
}
exclude_edge_keys={
    "selected",
    "animated",
    "className",
    "style",
}


def filter_json(flow_data: dict):
    """Filters the flow data in-place to exclude transient UI state for version comparison."""
    flow_data.pop("viewport", None)
    flow_data.pop("chatHistory", None)

    if "nodes" in flow_data:
        filter_nodes(flow_data["nodes"])
    if "edges" in flow_data:
        filter_dict_list(flow_data["edges"], exclude_keys=exclude_edge_keys)


def filter_nodes(nodes: list):
    """Filters the items in the data[field_name] list in-place to exclude the keys in exclude_keys.

    Throws an error if exclude_keys or field_name are not provided.
    """
    for item in nodes:
        if not item.get("data", {}).get("node", {}):
            continue
        filter_dict(
            item["data"]["node"].get("template", {}),
            exclude_node_keys["template"]
        )
        filter_node_recursive(
            item["data"]["node"].get("template", {}),
            exclude_node_keys["__recursive__"]
            )
        filter_dict_list(
            item["data"]["node"].get("outputs", []),
            exclude_node_keys["outputs"]
        )
        filter_dict(
            item,
            exclude_node_keys["__top_level__"]
        )
        filter_node_recursive(item, exclude_node_keys["__recursive__"])
        item["data"]["node"].pop("last_updated", None)
    return nodes


def filter_dict_list(items: list[dict], exclude_keys: set):
    items = [filter_dict(item, exclude_keys=exclude_keys) for item in items]


def filter_dict(d : dict, exclude_keys : set):
    for key in exclude_keys:
        d.pop(key, None)
    return d

def filter_node_recursive(d, exclude_keys):
    if isinstance(d, dict):
        for key in exclude_keys:
            d.pop(key, None)
        d = {k: filter_node_recursive(v, exclude_keys) for (k,v) in d.items()}
    elif isinstance(d, list):
        d = [filter_node_recursive(item, exclude_keys) for item in d]
    return d


def compute_dict_hash(flow_data: dict, old_or_new: str | None = None):
    """Computes the hash of the flow data."""
    filter_json(flow_data_copy := flow_data.copy())
    # print('WOWOWOW FILTER JSON', flow_data_copy["nodes"])
    cleaned_flow_json = orjson_dumps(flow_data_copy, sort_keys=True)
    import json

    if old_or_new == "old":
        with open("old_flow_data.json", "w") as f:
            f.write(cleaned_flow_json)
    if old_or_new == "new":
        with open("new_flow_data.json", "w") as f:
            f.write(cleaned_flow_json)

    return hashlib.sha256(cleaned_flow_json.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    d = {'foo': 1, 'bar': 2}
    exclude = 'bar'
    filter_dict(d, exclude)