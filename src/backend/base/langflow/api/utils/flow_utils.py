"""Flow graph building, cascade deletion, and public flow verification utilities."""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING, Literal

from fastapi import HTTPException
from lfx.graph.graph.base import Graph
from lfx.services.deps import session_scope
from sqlalchemy import delete
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.authorization.public_access import (
    PublicResourceAction,
    authorize_public_flow_access,
    public_execution_user,
)
from langflow.services.database.models.auth.authz import AuthzShare
from langflow.services.database.models.deployment.exceptions import (
    araise_if_deployment_guard_error_or_skip,
)
from langflow.services.database.models.deployment.guards import check_flow_has_deployed_versions
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.traces.model import SpanTable, TraceTable
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.user.model import UserRead
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
    # Pin the caller's run_id before initialize_run so HITL resume reuses the pre-pause trace.
    if (caller_run_id := kwargs.get("run_id")) is not None:
        graph.set_run_id(caller_run_id)
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
        await check_flow_has_deployed_versions(session, flow_id=flow_id)
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
        # span.trace_id FK lacks ON DELETE CASCADE in the DDL, so spans must
        # be removed before traces to avoid an FK violation under
        # PRAGMA foreign_keys=ON.
        trace_ids = (await session.exec(select(TraceTable.id).where(TraceTable.flow_id == flow_id))).all()
        if trace_ids:
            await session.exec(delete(SpanTable).where(col(SpanTable.trace_id).in_(trace_ids)))
            await session.exec(delete(TraceTable).where(col(TraceTable.id).in_(trace_ids)))
        # authz_share is polymorphic over resource_type/resource_id with no
        # FK, so DB cascades cannot remove stale share rows when the flow is
        # deleted. Clean them up here so a deleted flow's grants do not
        # silently survive — that would let an authorization plugin keep
        # honoring share rows that point at a tombstoned resource.
        await session.exec(
            delete(AuthzShare).where(AuthzShare.resource_type == "flow").where(AuthzShare.resource_id == flow_id)
        )
        await session.exec(delete(Flow).where(Flow.id == flow_id))
    except Exception as e:
        await araise_if_deployment_guard_error_or_skip(
            e,
            log_message=f"op=cascade_delete_flow flow_id={flow_id}",
        )
        msg = f"Unable to cascade delete flow: {flow_id}"
        raise RuntimeError(msg, e) from e


# Public flow file paths must be ``{source_flow_id}/{safe_basename}`` — uploads
# under that namespace are the only legitimate inputs for an unauthenticated
# build. Anything else (absolute paths, traversal, foreign flow_ids) is a
# probe at the arbitrary-file-read class of bug (GHSA-rcjh-r59h-gq37).
_PUBLIC_FILE_PATH_RE = re.compile(
    r"^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})/([^/\\]+)$"
)
_PUBLIC_FILE_REJECTED_SUBSTRINGS = ("\x00", "..", "\\")


def validate_public_files(files: list[str] | None, source_flow_id: uuid.UUID) -> None:
    """Reject file references that aren't ``{source_flow_id}/{basename}``.

    Mitigates GHSA-rcjh-r59h-gq37: an unauthenticated build must not be
    able to address files outside its own flow's storage namespace.
    Called from any endpoint that accepts caller-supplied file references
    under a public-access boundary.
    """
    if not files:
        return
    expected_flow_id = str(source_flow_id).lower()
    for entry in files:
        if not isinstance(entry, str) or not entry:
            raise HTTPException(status_code=400, detail="Invalid file entry")
        if any(token in entry for token in _PUBLIC_FILE_REJECTED_SUBSTRINGS):
            raise HTTPException(status_code=400, detail="Invalid file path")
        match = _PUBLIC_FILE_PATH_RE.match(entry)
        if not match:
            raise HTTPException(status_code=400, detail="Invalid file path format")
        flow_id_segment, basename = match.group(1), match.group(2)
        if flow_id_segment.lower() != expected_flow_id:
            raise HTTPException(status_code=400, detail="File not in this flow's namespace")
        if basename in (".", ".."):
            raise HTTPException(status_code=400, detail="Invalid filename")


def compute_virtual_flow_id(
    identifier: str | uuid.UUID,
    flow_id: uuid.UUID,
    *,
    principal_type: Literal["user", "client"] | None = None,
) -> uuid.UUID:
    """Compute a deterministic virtual flow ID for session/message isolation.

    Args:
        identifier: A unique identifier (user_id for authenticated users, client_id for anonymous).
        flow_id: The original flow ID.
        principal_type: Optional identity domain for public-flow callers. Authenticated
            user IDs and anonymous client IDs must never share a UUID namespace.

    Returns:
        A deterministic UUID v5 derived from the identifier and flow_id.
    """
    namespaced_identifier = f"{principal_type}:{identifier}" if principal_type else str(identifier)
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"{namespaced_identifier}_{flow_id}")


def scope_session_to_namespace(session: str | None, namespace: str) -> str | None:
    """Wrap a caller-supplied session ID under a (client_id, flow_id) namespace.

    Mitigates CVE-2026-33017: an unauthenticated public-flow caller cannot
    address a session that lives outside its own namespace through a Memory
    component, regardless of whether the caller supplies a non-empty,
    pre-prefixed, or empty string.

    Returns ``None`` unchanged. Returns the value unchanged when it equals the
    namespace or already starts with ``f"{namespace}:"``. Otherwise prefixes
    it -- including the empty-string case, which becomes ``f"{namespace}:"``.
    """
    if session is None:
        return session
    prefix = f"{namespace}:"
    if session == namespace or session.startswith(prefix):
        return session
    return f"{prefix}{session}"


async def verify_public_flow_and_get_user(
    flow_id: uuid.UUID,
    client_id: str | None,
    authenticated_user_id: uuid.UUID | None = None,
    request_host: str | None = None,
) -> tuple[UserRead, uuid.UUID]:
    """Verify a public flow request and generate a deterministic flow ID.

    This utility function:
    1. Checks that a client_id cookie or authenticated_user_id is provided
    2. Verifies an explicit or compatibility-derived PUBLIC grant
    3. Creates a deterministic UUID based on the identifier and original flow_id
    4. Returns the stable non-user execution principal

    When an authenticated_user_id is provided, it takes precedence over client_id
    for UUID v5 generation. This enables DB-persisted sessions for logged-in users
    on the shareable playground.

    Args:
        flow_id: The original flow ID to verify
        client_id: The client ID from the request cookie
        authenticated_user_id: The authenticated user's ID (takes precedence over client_id)
        request_host: Trusted request hostname supplied to the tenant-resolution plugin seam.

    Returns:
        tuple: (anonymous execution principal, deterministic flow ID for tracking)

    Raises:
        HTTPException:
            - 400 if neither client_id nor authenticated_user_id is provided
            - 404 if the flow or its direct-link grant is unavailable
    """
    if not client_id and not authenticated_user_id:
        raise HTTPException(status_code=400, detail="No client_id cookie found")

    # Load only the exact direct-link resource; this path never enumerates flows.
    async with session_scope() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == flow_id))).first()
        if flow is None:
            raise HTTPException(status_code=404, detail="Flow not found")
        await authorize_public_flow_access(
            flow=flow,
            action=PublicResourceAction.EXECUTE,
            request_host=request_host,
            session=session,
        )

    # Use authenticated user_id for deterministic UUID when available, otherwise client_id.
    # Keep the branches explicit so identifier is non-optional at the UUID boundary.
    if authenticated_user_id is not None:
        identifier = str(authenticated_user_id)
        principal_type: Literal["user", "client"] = "user"
    else:
        if client_id is None:
            raise HTTPException(status_code=400, detail="No client_id cookie found")
        identifier = client_id
        principal_type = "client"
    new_flow_id = compute_virtual_flow_id(identifier, flow_id, principal_type=principal_type)

    return public_execution_user(), new_flow_id
