"""Flow graph building, cascade deletion, and public flow verification utilities."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import HTTPException
from lfx.graph.graph.base import Graph
from lfx.log.logger import logger
from lfx.services.deps import session_scope
from sqlalchemy import delete
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.user.model import User
from langflow.services.database.models.vertex_builds.model import VertexBuildTable

if TYPE_CHECKING:
    from langflow.services.chat.service import ChatService


async def _get_flow_name(flow_id: uuid.UUID) -> str:
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        if flow is None:
            msg = f"Flow {flow_id} not found"
            raise ValueError(msg)
    return flow.name


async def build_graph_from_data(flow_id: uuid.UUID | str, payload: dict, **kwargs):
    """Build and cache the graph."""
    # Get flow name
    if "flow_name" not in kwargs:
        flow_name = await _get_flow_name(flow_id if isinstance(flow_id, uuid.UUID) else uuid.UUID(flow_id))
    else:
        flow_name = kwargs["flow_name"]
    str_flow_id = str(flow_id)
    session_id = kwargs.get("session_id") or str_flow_id

    graph = Graph.from_payload(payload, str_flow_id, flow_name, kwargs.get("user_id"))
    for vertex_id in graph.has_session_id_vertices:
        vertex = graph.get_vertex(vertex_id)
        if vertex is None:
            msg = f"Vertex {vertex_id} not found"
            raise ValueError(msg)
        if not vertex.raw_params.get("session_id"):
            vertex.update_raw_params({"session_id": session_id}, overwrite=True)

    graph.session_id = session_id
    await graph.initialize_run()
    return graph


async def build_graph_from_db_no_cache(flow_id: uuid.UUID, session: AsyncSession, **kwargs):
    """Build and cache the graph."""
    flow: Flow | None = await session.get(Flow, flow_id)
    if not flow or not flow.data:
        msg = "Invalid flow ID"
        raise ValueError(msg)
    kwargs["user_id"] = kwargs.get("user_id") or str(flow.user_id)
    return await build_graph_from_data(flow_id, flow.data, flow_name=flow.name, **kwargs)


async def build_graph_from_db(flow_id: uuid.UUID, session: AsyncSession, chat_service: ChatService, **kwargs):
    graph = await build_graph_from_db_no_cache(flow_id=flow_id, session=session, **kwargs)
    await chat_service.set_cache(str(flow_id), graph)
    return graph


async def build_and_cache_graph_from_data(
    flow_id: uuid.UUID | str,
    chat_service: ChatService,
    graph_data: dict,
):  # -> Graph | Any:
    """Build and cache the graph."""
    # Convert flow_id to str if it's UUID
    str_flow_id = str(flow_id) if isinstance(flow_id, uuid.UUID) else flow_id
    graph = Graph.from_payload(graph_data, str_flow_id)
    await chat_service.set_cache(str_flow_id, graph)
    return graph


async def cascade_delete_flow(session: AsyncSession, flow_id: uuid.UUID) -> None:
    try:
        # TODO: Verify if deleting messages is safe in terms of session id relevance
        # If we delete messages directly, rather than setting flow_id to null,
        # it might cause unexpected behaviors because the session id could still be
        # used elsewhere to search for these messages.
        await session.exec(delete(MessageTable).where(MessageTable.flow_id == flow_id))
        await session.exec(delete(TransactionTable).where(TransactionTable.flow_id == flow_id))
        await session.exec(delete(VertexBuildTable).where(VertexBuildTable.flow_id == flow_id))
        # Explicit delete despite FK CASCADE -- SQLite doesn't enforce FK cascades
        # by default (requires PRAGMA foreign_keys = ON), and this function follows
        # the existing pattern of explicitly deleting all child records.
        await session.exec(delete(FlowVersion).where(FlowVersion.flow_id == flow_id))
        await session.exec(delete(Flow).where(Flow.id == flow_id))
    except Exception as e:
        msg = f"Unable to cascade delete flow: {flow_id}"
        raise RuntimeError(msg, e) from e


def compute_virtual_flow_id(identifier: str | uuid.UUID, flow_id: uuid.UUID) -> uuid.UUID:
    """Compute a deterministic virtual flow ID for session/message isolation.

    Args:
        identifier: A unique identifier (user_id for authenticated users, client_id for anonymous).
        flow_id: The original flow ID.

    Returns:
        A deterministic UUID v5 derived from the identifier and flow_id.
    """
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"{identifier}_{flow_id}")


async def verify_public_flow_and_get_user(
    flow_id: uuid.UUID,
    client_id: str | None,
    authenticated_user_id: uuid.UUID | None = None,
) -> tuple[User, uuid.UUID]:
    """Verify a public flow request and generate a deterministic flow ID.

    This utility function:
    1. Checks that a client_id cookie or authenticated_user_id is provided
    2. Verifies the flow exists and is marked as PUBLIC
    3. Creates a deterministic UUID based on the identifier and original flow_id
    4. Retrieves the flow owner user for permission purposes

    When an authenticated_user_id is provided, it takes precedence over client_id
    for UUID v5 generation. This enables DB-persisted sessions for logged-in users
    on the shareable playground.

    Args:
        flow_id: The original flow ID to verify
        client_id: The client ID from the request cookie
        authenticated_user_id: The authenticated user's ID (takes precedence over client_id)

    Returns:
        tuple: (flow owner user, deterministic flow ID for tracking)

    Raises:
        HTTPException:
            - 400 if neither client_id nor authenticated_user_id is provided
            - 403 if flow doesn't exist or isn't public
            - 403 if unable to retrieve the flow owner user
            - 403 if user is not found for public flow
    """
    if not client_id and not authenticated_user_id:
        raise HTTPException(status_code=400, detail="No client_id cookie found")

    # Check if the flow is public
    async with session_scope() as session:
        from sqlmodel import select

        from langflow.services.database.models.flow.model import AccessTypeEnum, Flow

        flow = (await session.exec(select(Flow).where(Flow.id == flow_id))).first()
        if not flow or flow.access_type is not AccessTypeEnum.PUBLIC:
            raise HTTPException(status_code=403, detail="Flow is not public")

    # Use authenticated user_id for deterministic UUID when available, otherwise client_id
    identifier = str(authenticated_user_id) if authenticated_user_id else client_id
    new_flow_id = compute_virtual_flow_id(identifier, flow_id)

    # Get the user associated with the flow
    try:
        from langflow.helpers.user import get_user_by_flow_id_or_endpoint_name

        user = await get_user_by_flow_id_or_endpoint_name(str(flow_id))

    except Exception as exc:
        await logger.aexception("Error getting user for public flow %s", flow_id)
        raise HTTPException(status_code=403, detail="Flow is not accessible") from exc

    if not user:
        raise HTTPException(status_code=403, detail="Flow is not accessible")

    return user, new_flow_id
