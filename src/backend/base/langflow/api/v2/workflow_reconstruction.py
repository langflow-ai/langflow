"""Workflow response reconstruction from vertex_build table.

This module reconstructs WorkflowExecutionResponse from vertex_build table data by job_id,
enabling retrieval of past execution results without re-running workflows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.graph.graph.base import Graph
from lfx.graph.schema import ResultData, RunOutputs
from lfx.workflow.converters import run_response_to_workflow_response

from langflow.api.v1.schemas import RunResponse
from langflow.services.database.models.vertex_builds.crud import get_vertex_builds_by_job_id

if TYPE_CHECKING:
    from lfx.services.database.models.flow import FlowRead
    from sqlmodel.ext.asyncio.session import AsyncSession

# Bound the structured search so a pathological/cyclic payload can't recurse
# unboundedly; the session_id sits a few levels deep in the persisted Message.
_SESSION_ID_SEARCH_MAX_DEPTH = 8


def _recover_session_id(value: object, depth: int = 0) -> str | None:
    """Find the session_id persisted in a terminal vertex_build's structured data.

    The session is serialized inside the terminal Message (e.g.
    ``results["message"]["data"]["session_id"]`` and the output rows) at a depth
    that varies by component, so search the dict/list structure rather than
    depending on one component's layout. Serialized text blobs are strings, not
    walked, so table headers that merely contain the word "session_id" are ignored.
    """
    if depth > _SESSION_ID_SEARCH_MAX_DEPTH:
        return None
    if isinstance(value, dict):
        candidate = value.get("session_id")
        if isinstance(candidate, str) and candidate:
            return candidate
        for nested in value.values():
            found = _recover_session_id(nested, depth + 1)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _recover_session_id(item, depth + 1)
            if found:
                return found
    return None


async def reconstruct_workflow_response_from_job_id(
    session: AsyncSession,
    flow: FlowRead,
    job_id: str,
    user_id: str,
):
    """Reconstruct WorkflowExecutionResponse from vertex_builds by job_id.

    Args:
        session: Database session (readonly for performance)
        flow: Flow model from database
        job_id: Job ID to query vertex builds
        user_id: User ID for graph construction

    Returns:
        WorkflowExecutionResponse reconstructed from vertex_build data

    Raises:
        ValueError: If flow has no data or no vertex builds found for job_id
    """
    # Validate flow data
    if not flow.data:
        msg = f"Flow {flow.id} has no data"
        raise ValueError(msg)

    # Query vertex_builds by job_id
    vertex_builds = await get_vertex_builds_by_job_id(session, job_id)
    if not vertex_builds:
        msg = f"No vertex builds found for job_id {job_id}"
        raise ValueError(msg)

    # Build graph to identify terminal nodes
    flow_id_str = str(flow.id)
    graph = Graph.from_payload(flow.data, flow_id=flow_id_str, user_id=user_id, flow_name=flow.name)
    terminal_node_ids = graph.get_terminal_nodes()

    # Filter to terminal vertices with data
    terminal_vertex_builds = [vb for vb in vertex_builds if vb.id in terminal_node_ids and vb.data]
    if not terminal_vertex_builds:
        msg = f"No terminal vertex builds found for job_id {job_id}"
        raise ValueError(msg)

    # Convert vertex_build data to RunOutputs format
    run_outputs_list = [RunOutputs(inputs={}, outputs=[ResultData(**vb.data)]) for vb in terminal_vertex_builds]

    # Recover the session_id the run executed under so GET status can continue the
    # same chat/memory thread, instead of always reporting null. It is persisted
    # inside the terminal Message (``results[...]["data"]["session_id"]``) at a
    # depth that varies by component, so search the structured data. A data-only
    # flow has no session to recover and correctly stays None.
    session_id = next(
        (sid for vb in terminal_vertex_builds if (sid := _recover_session_id(vb.data))),
        None,
    )

    # Create RunResponse and convert to WorkflowExecutionResponse
    run_response = RunResponse(outputs=run_outputs_list, session_id=session_id)

    return run_response_to_workflow_response(
        run_response=run_response,
        flow_id=flow_id_str,
        job_id=job_id,
        inputs={},
        graph=graph,
    )
