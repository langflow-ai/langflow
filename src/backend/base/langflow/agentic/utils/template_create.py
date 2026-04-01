"""Utilities to create flows from starter templates.

This module provides a helper to create a new Flow from a starter template
JSON (looked up by template id) and returns a link to open it in the UI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import HTTPException

from langflow.agentic.utils.template_search import get_template_by_id
from langflow.api.v1.flows import _new_flow, _save_flow_to_fs
from langflow.initial_setup.setup import get_or_create_default_folder
from langflow.services.database.models.flow.model import FlowCreate
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import get_storage_service

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


async def create_flow_from_template_and_get_link(
    *,
    session: AsyncSession,
    user_id: UUID,
    template_id: str,
    target_folder_id: UUID | None = None,
) -> dict[str, Any]:
    """Create a new flow from a starter template and return its id and UI link.

    Args:
        session: Active async DB session.
        user_id: The owner user id for the new flow.
        template_id: The string id field inside the starter template JSON.
        target_folder_id: Optional folder id to place the flow. If not provided,
            the user's default folder will be used.

    Returns:
        Dict with keys: {"id": str, "link": str}
    """
    # 1) Load template JSON from starter_projects
    template = get_template_by_id(template_id=template_id, fields=None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # 2) Resolve target folder
    if target_folder_id:
        folder = await session.get(Folder, target_folder_id)
        if not folder or folder.user_id != user_id:
            raise HTTPException(status_code=400, detail="Invalid target folder")
        folder_id = folder.id
    else:
        default_folder = await get_or_create_default_folder(session, user_id)
        folder_id = default_folder.id

    # 3) Build FlowCreate from template fields (ignore unknowns)
    new_flow = FlowCreate(
        name=template.get("name"),
        description=template.get("description"),
        icon=template.get("icon"),
        icon_bg_color=template.get("icon_bg_color"),
        gradient=template.get("gradient"),
        data=template.get("data"),
        is_component=template.get("is_component", False),
        endpoint_name=template.get("endpoint_name"),
        tags=template.get("tags"),
        mcp_enabled=template.get("mcp_enabled"),
        folder_id=folder_id,
        user_id=user_id,
    )

    # 4) Use the same creation path as API
    storage_service = get_storage_service()
    db_flow = await _new_flow(session=session, flow=new_flow, user_id=user_id, storage_service=storage_service)
    await session.commit()
    await session.refresh(db_flow)
    await _save_flow_to_fs(db_flow, user_id, storage_service)

    # 5) Build relative UI link
    link = f"/flow/{db_flow.id}/folder/{folder_id}"
    return {"id": str(db_flow.id), "link": link}
