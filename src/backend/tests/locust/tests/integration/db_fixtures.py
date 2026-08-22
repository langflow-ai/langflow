"""Insert/delete performance-suite flows and projects in the live test DB.

Support helpers for ``test_subsystem_coverage`` (and any future integration
tests) that need a flow/project row before calling workflows, webhook, or MCP.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from lfx.services.deps import session_scope


async def insert_project(*, user_id: Any, name: str | None = None) -> UUID:
    project_id = uuid4()
    async with session_scope() as session:
        session.add(Folder(id=project_id, name=name or f"perf-project-{project_id.hex[:8]}", user_id=user_id))
        await session.flush()
    return project_id


async def delete_project(project_id: UUID) -> None:
    async with session_scope() as session:
        project = await session.get(Folder, project_id)
        if project:
            await session.delete(project)


async def insert_flow(
    *,
    user_id: Any,
    payload: dict[str, Any],
    name: str | None = None,
    endpoint_name: str | None = None,
    folder_id: UUID | None = None,
    mcp_enabled: bool = False,
    action_name: str | None = None,
) -> UUID:
    flow_id = uuid4()
    async with session_scope() as session:
        session.add(
            Flow(
                id=flow_id,
                name=name or payload.get("name") or f"perf-{flow_id}",
                description=payload.get("description") or "performance-suite fixture",
                data=payload.get("data", payload),
                endpoint_name=endpoint_name or payload.get("endpoint_name"),
                user_id=user_id,
                folder_id=folder_id,
                mcp_enabled=mcp_enabled,
                action_name=action_name or payload.get("name") or name,
            )
        )
        await session.flush()
    return flow_id


async def delete_flow(flow_id: UUID) -> None:
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        if flow:
            await session.delete(flow)
