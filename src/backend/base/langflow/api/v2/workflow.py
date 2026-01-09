"""V2 Workflow execution endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from lfx.graph.graph.base import Graph
from lfx.schema.workflow import (
    WORKFLOW_EXECUTION_RESPONSES,
    WORKFLOW_STATUS_RESPONSES,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowJobResponse,
    WorkflowStopRequest,
    WorkflowStopResponse,
)
from lfx.services.deps import get_settings_service

from langflow.api.v1.schemas import RunResponse
from langflow.api.v2.converters import (
    create_error_response,
    parse_flat_inputs,
    run_response_to_workflow_response,
)
from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.processing.process import process_tweaks, run_graph_internal
from langflow.services.auth.utils import api_key_security
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import UserRead


def check_developer_api_enabled() -> None:
    """Check if developer API is enabled, raise HTTPException if not."""
    settings = get_settings_service().settings
    if not settings.developer_api_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This endpoint is not available",
        )


router = APIRouter(prefix="/workflow", tags=["Workflow"], dependencies=[Depends(check_developer_api_enabled)])


@router.post(
    "",
    response_model=None,
    response_model_exclude_none=True,
    responses=WORKFLOW_EXECUTION_RESPONSES,
    summary="Execute Workflow",
    description="Execute a workflow with support for sync, stream, and background modes",
)
async def execute_workflow(
    workflow_request: WorkflowExecutionRequest,
    background_tasks: BackgroundTasks,
    api_key_user: Annotated[UserRead, Depends(api_key_security)],
) -> WorkflowExecutionResponse | WorkflowJobResponse | StreamingResponse:
    """Execute a workflow with multiple execution modes.

    - **sync**: Returns complete results immediately (background=False, stream=False)
    - **stream**: Returns server-sent events in real-time (stream=True)
    - **background**: Starts job and returns job ID immediately (background=True)
    """
    # Validate flow exists and user has permission
    flow = await get_flow_by_id_or_endpoint_name(workflow_request.flow_id, api_key_user.id)
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Flow identifier {workflow_request.flow_id} not found"
        )

    # Generate job_id for tracking
    job_id = str(uuid4())

    # Phase 1: Sync mode only (stream=false, background=false)
    if not workflow_request.stream and not workflow_request.background:
        return await execute_sync_workflow(
            workflow_request=workflow_request,
            flow=flow,
            job_id=job_id,
            api_key_user=api_key_user,
            background_tasks=background_tasks,
        )

    # Phase 2: Background mode (to be implemented)
    if workflow_request.background:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Background execution not yet implemented"
        )

    # Phase 3: Streaming mode (to be implemented)
    # This should never be reached due to the conditions above, but included for completeness
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Streaming execution not yet implemented")


async def execute_sync_workflow(
    workflow_request: WorkflowExecutionRequest,
    flow: Flow,
    job_id: str,
    api_key_user: UserRead,
    background_tasks: BackgroundTasks,  # noqa: ARG001
) -> WorkflowExecutionResponse:
    """Execute workflow synchronously and return complete results.

    Args:
        workflow_request: The workflow execution request
        flow: The flow to execute
        job_id: Generated job ID for tracking
        api_key_user: Authenticated user
        background_tasks: FastAPI background tasks

    Returns:
        WorkflowExecutionResponse with complete results
    """
    try:
        # Parse flat inputs structure
        tweaks, session_id = parse_flat_inputs(workflow_request.inputs or {})

        # Validate flow data
        if flow.data is None:
            msg = f"Flow {flow.id} has no data"
            raise ValueError(msg)

        # Build the graph once
        flow_id_str = str(flow.id)
        user_id = str(api_key_user.id)
        graph_data = flow.data.copy()
        graph_data = process_tweaks(graph_data, tweaks, stream=False)
        graph = Graph.from_payload(graph_data, flow_id=flow_id_str, user_id=user_id, flow_name=flow.name)

        # Get terminal nodes - these are the outputs we want
        terminal_node_ids = graph.get_terminal_nodes()

        # Execute the graph directly with terminal nodes as outputs
        # No need to pass inputs - tweaks handle everything including input_value
        task_result, execution_session_id = await run_graph_internal(
            graph=graph,
            flow_id=flow_id_str,
            session_id=session_id,
            inputs=None,
            outputs=terminal_node_ids,
            stream=False,
        )

        # Build RunResponse
        run_response = RunResponse(outputs=task_result, session_id=execution_session_id)

        # Convert to WorkflowExecutionResponse
        return run_response_to_workflow_response(
            run_response=run_response,
            flow_id=workflow_request.flow_id,
            job_id=job_id,
            workflow_request=workflow_request,
            graph=graph,
        )

    except Exception as exc:  # noqa: BLE001
        # Convert to workflow error format - catch all exceptions to provide consistent error responses
        return create_error_response(
            flow_id=workflow_request.flow_id,
            job_id=job_id,
            workflow_request=workflow_request,
            error=exc,
        )


@router.get(
    "",
    response_model=None,
    response_model_exclude_none=True,
    responses=WORKFLOW_STATUS_RESPONSES,
    summary="Get Workflow Status",
    description="Get status of workflow job by job ID",
)
async def get_workflow_status(
    api_key_user: Annotated[UserRead, Depends(api_key_security)],  # noqa: ARG001
    job_id: Annotated[str, Query(description="Job ID to query")],  # noqa: ARG001
) -> WorkflowExecutionResponse | StreamingResponse:
    """Get workflow job status and results by job ID."""
    # TODO: Implementation
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented /status yet")


@router.post(
    "/stop",
    response_model=WorkflowStopResponse,
    summary="Stop Workflow",
    description="Stop a running workflow execution",
)
async def stop_workflow(
    request: WorkflowStopRequest,  # noqa: ARG001
    api_key_user: Annotated[UserRead, Depends(api_key_security)],  # noqa: ARG001
) -> WorkflowStopResponse:
    """Stop a running workflow execution by job_id.

    Parameters:
    - job_id: The specific job ID to stop
    - force: Whether to force stop the workflow (optional)
    """
    # TODO: Implementation
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented /stop yet")
