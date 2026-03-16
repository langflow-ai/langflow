"""Workflow response reconstruction from vertex_build table.

This module reconstructs WorkflowExecutionResponse from vertex_build table data by job_id,
enabling retrieval of past execution results without re-running workflows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.graph.graph.base import Graph
from lfx.graph.schema import ResultData, RunOutputs
from lfx.schema.workflow import WorkflowExecutionRequest

from langflow.api.v1.schemas import RunResponse
from langflow.api.v2.converters import run_response_to_workflow_response
from langflow.services.database.models.vertex_builds.crud import get_vertex_builds_by_job_id

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.flow.model import FlowRead


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

    # Create RunResponse and convert to WorkflowExecutionResponse
    run_response = RunResponse(outputs=run_outputs_list, session_id=None)
    workflow_request = WorkflowExecutionRequest(flow_id=flow_id_str, inputs={})

    return run_response_to_workflow_response(
        run_response=run_response,
        flow_id=flow_id_str,
        job_id=job_id,
        workflow_request=workflow_request,
        graph=graph,
    )
