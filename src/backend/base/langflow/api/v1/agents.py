"""Agent Builder API router — CRUD, tools listing, and chat streaming."""

import uuid as uuid_mod
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from lfx.base.models.unified_models import get_all_variables_for_provider
from lfx.interface.components import get_and_cache_all_types_dict
from lfx.log.logger import logger

from langflow.api.utils.core import CurrentActiveUser, DbSession
from langflow.services.agent_builder.chat_service import (
    resolve_provider_and_model,
    stream_agent_chat,
)
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.agents.crud import (
    create_agent,
    delete_agent,
    get_agent_by_id,
    get_agents_by_user,
    update_agent,
)
from langflow.services.database.models.agents.schema import (
    AgentCreate,
    AgentRead,
    AgentUpdate,
)
from langflow.services.deps import get_settings_service

router = APIRouter(prefix="/agents", tags=["Agents"])

TOOLS_CATEGORY = "tools"


@router.get("/tools", dependencies=[Depends(get_current_active_user)])
async def get_available_tools() -> list[dict]:
    """List all components usable as agent tools.

    Returns components grouped by category, with the 'tools' category
    flagged as suggested.
    """
    all_types = await get_and_cache_all_types_dict(settings_service=get_settings_service())

    tools: list[dict] = []
    for category_name, components in all_types.items():
        for comp_name, comp_data in components.items():
            tools.append(
                {
                    "class_name": comp_name,
                    "display_name": comp_data.get("display_name", comp_name),
                    "description": comp_data.get("description", ""),
                    "icon": comp_data.get("icon", ""),
                    "category": category_name,
                    "is_suggested": category_name == TOOLS_CATEGORY,
                }
            )

    tools.sort(key=lambda t: (not t["is_suggested"], t["category"], t["display_name"]))
    return tools


@router.get("/")
async def list_agents(current_user: CurrentActiveUser, db: DbSession) -> list[AgentRead]:
    """List all agents for the current user."""
    agents = await get_agents_by_user(db, current_user.id)
    return [AgentRead.model_validate(a) for a in agents]


@router.post("/", status_code=201)
async def create_agent_endpoint(
    data: AgentCreate,
    current_user: CurrentActiveUser,
    db: DbSession,
) -> AgentRead:
    """Create a new agent configuration."""
    agent = await create_agent(db, current_user.id, data)
    logger.info(f"Agent created: agent_id={agent.id}, user_id={current_user.id}")
    return AgentRead.model_validate(agent)


@router.get("/{agent_id}")
async def get_agent_endpoint(
    agent_id: UUID,
    current_user: CurrentActiveUser,
    db: DbSession,
) -> AgentRead:
    """Get a single agent by ID."""
    agent = await get_agent_by_id(db, agent_id, current_user.id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return AgentRead.model_validate(agent)


@router.patch("/{agent_id}")
async def update_agent_endpoint(
    agent_id: UUID,
    data: AgentUpdate,
    current_user: CurrentActiveUser,
    db: DbSession,
) -> AgentRead:
    """Update an existing agent."""
    agent = await update_agent(db, agent_id, current_user.id, data)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return AgentRead.model_validate(agent)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent_endpoint(
    agent_id: UUID,
    current_user: CurrentActiveUser,
    db: DbSession,
) -> None:
    """Delete an agent."""
    deleted = await delete_agent(db, agent_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found.")


@router.post("/{agent_id}/chat/stream")
async def agent_chat_stream(
    agent_id: UUID,
    http_request: Request,
    current_user: CurrentActiveUser,
    db: DbSession,
    input_value: str = "",
    provider: str | None = None,
    model_name: str | None = None,
    session_id: str | None = None,
) -> StreamingResponse:
    """Stream chat with an agent via SSE."""
    agent = await get_agent_by_id(db, agent_id, current_user.id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found.")

    resolved_provider, resolved_model = await resolve_provider_and_model(
        user_id=current_user.id,
        session=db,
        provider=provider,
        model_name=model_name,
    )

    provider_vars = get_all_variables_for_provider(current_user.id, resolved_provider)
    global_vars: dict[str, str] = {
        "USER_ID": str(current_user.id),
        "MODEL_NAME": resolved_model,
        "PROVIDER": resolved_provider,
    }
    global_vars.update(provider_vars)

    effective_session_id = session_id or str(uuid_mod.uuid4())

    return StreamingResponse(
        stream_agent_chat(
            system_prompt=agent.system_prompt,
            tool_components=agent.tool_components,
            input_value=input_value,
            provider=resolved_provider,
            model_name=resolved_model,
            user_id=str(current_user.id),
            session_id=effective_session_id,
            global_variables=global_vars,
            is_disconnected=http_request.is_disconnected,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
