"""V2 Workflow execution endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
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

from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.services.auth.utils import api_key_security
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
    background_tasks: BackgroundTasks,  # noqa: ARG001
    api_key_user: Annotated[UserRead, Depends(api_key_security)],
) -> WorkflowExecutionResponse | WorkflowJobResponse | StreamingResponse:
    """Execute a workflow with multiple execution modes.

    - **sync**: Returns complete results immediately (background=False, stream=False)
    - **stream**: Returns server-sent events in real-time (stream=True)
    - **background**: Starts job and returns job ID immediately (background=True)
    """
    flow = await get_flow_by_id_or_endpoint_name(workflow_request.flow_id, api_key_user.id)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Flow {workflow_request.flow_id} not found")

    # TODO: Implementation
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented /workflow execution yet")


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
