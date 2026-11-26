"""Routes specific to the built-in Agent Harness."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from lfx.projects.builtins import AGENT_HARNESS
from sqlmodel import col, select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.project_type_guards import require_project_type
from langflow.services.database.models.flow.model import Flow

router = APIRouter()
_harness_project = require_project_type(AGENT_HARNESS.name, owner_only=True)


@router.get("/{project_id}/tool-definitions")
async def read_local_tool_definitions(*, session: DbSession, project_id: UUID, current_user: CurrentActiveUser):
    """Return authorized, statically validated local tool definitions for explicit review."""
    from lfx.projects.local_tools import local_tool_definition

    from langflow.services.database.models.folder.flow_bindings import flow_definitions, resolve_binding_flows

    await _harness_project(session=session, current_user=current_user, project_id=project_id)
    flows = (
        await session.exec(select(Flow).where(Flow.folder_id == project_id, col(Flow.is_component).is_(False)))
    ).all()
    definitions = []
    for flow in flows:
        try:
            sources = await resolve_binding_flows(session, current_user, flow)
            definition = local_tool_definition(flow_definitions([flow])[0], flow_definitions(sources.values()))
        except (ValueError, KeyError, TypeError, AttributeError, HTTPException):
            continue
        definitions.append(definition.model_dump(mode="json"))
    return sorted(definitions, key=lambda item: (item["name"], item["flow_id"]))
