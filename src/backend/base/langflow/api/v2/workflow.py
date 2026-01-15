"""V2 Workflow execution endpoints.

This module implements the V2 Workflow API endpoints for executing flows with
enhanced error handling, timeout protection, and structured responses.

Endpoints:
    POST /workflow: Execute a workflow (sync, stream, or background modes)
    GET /workflow: Get workflow job status by job_id
    POST /workflow/stop: Stop a running workflow execution

Features:
    - Developer API protection (requires developer_api_enabled setting)
    - Comprehensive error handling with structured error responses
    - Timeout protection for long-running executions
    - Support for multiple execution modes (sync, stream, background)
    - API key authentication required for all endpoints

Configuration:
    EXECUTION_TIMEOUT: Maximum execution time for synchronous workflows (300 seconds)
"""

from __future__ import annotations

import asyncio
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
from pydantic_core import ValidationError as PydanticValidationError
from sqlalchemy.exc import OperationalError

from langflow.api.v1.schemas import RunResponse
from langflow.api.v2.converters import (
    create_error_response,
    parse_flat_inputs,
    run_response_to_workflow_response,
)
from langflow.exceptions.api import WorkflowTimeoutError, WorkflowValidationError
from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.processing.process import process_tweaks, run_graph_internal
from langflow.services.auth.utils import api_key_security
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.database.models.user.model import UserRead

# Configuration constants
EXECUTION_TIMEOUT = 300  # 5 minutes default timeout for sync execution


def check_developer_api_enabled() -> None:
    """Check if developer API is enabled.

    This dependency function protects all workflow endpoints by verifying that
    the developer API feature is enabled in the application settings.

    Raises:
        HTTPException: 403 Forbidden if developer_api_enabled setting is False

    Note:
        This is used as a router-level dependency to protect all workflow endpoints.
    """
    settings = get_settings_service().settings
    if not settings.developer_api_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Developer API disabled",
                "code": "DEVELOPER_API_DISABLED",
                "message": "Developer API is not enabled. Contact administrator to enable this feature.",
            },
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
    """Execute a workflow with support for multiple execution modes.

    This endpoint supports three execution modes:
        - **Synchronous** (background=False, stream=False): Returns complete results immediately
        - **Streaming** (stream=True): Returns server-sent events in real-time (not yet implemented)
        - **Background** (background=True): Starts job and returns job ID (not yet implemented)

    Error Handling Strategy:
        - System errors (404, 500, 503, 504): Returned as HTTP error responses
        - Component execution errors: Returned as HTTP 200 with errors in response body

    Args:
        workflow_request: The workflow execution request containing flow_id, inputs, and mode flags
        background_tasks: FastAPI background tasks for async operations
        api_key_user: Authenticated user from API key

    Returns:
        - WorkflowExecutionResponse: For synchronous execution (HTTP 200)
        - WorkflowJobResponse: For background execution (HTTP 202, not yet implemented)
        - StreamingResponse: For streaming execution (not yet implemented)

    Raises:
        HTTPException:
            - 403: Developer API disabled
            - 404: Flow not found or user lacks access
            - 500: Invalid flow data or validation error
            - 501: Streaming or background mode not yet implemented
            - 503: Database unavailable
            - 504: Execution timeout exceeded
    """
    # Validate flow exists and user has permission
    try:
        flow = await get_flow_by_id_or_endpoint_name(workflow_request.flow_id, api_key_user.id)
    except HTTPException as e:
        # get_flow_by_id_or_endpoint_name raises HTTPException with string detail
        # Convert to structured format
        if e.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Flow not found",
                    "code": "FLOW_NOT_FOUND",
                    "message": f"Flow '{workflow_request.flow_id}' does not exist or you don't have access to it",
                    "flow_id": workflow_request.flow_id,
                },
            ) from e
        # Re-raise other HTTPExceptions as-is
        raise
    except PydanticValidationError as e:
        # Flow data validation errors (invalid flow structure)
        error_msg = f"Flow has invalid data structure: {e!s}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Invalid flow data",
                "code": "INVALID_FLOW_DATA",
                "message": error_msg,
                "flow_id": workflow_request.flow_id,
            },
        ) from e
    except OperationalError as e:
        # Database errors specifically
        error_msg = f"Failed to fetch flow: {e!s}"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Service unavailable",
                "code": "DATABASE_ERROR",
                "message": error_msg,
                "flow_id": workflow_request.flow_id,
            },
        ) from e

    # Generate job_id for tracking
    job_id = str(uuid4())

    # Phase 1: Background mode (to be implemented)
    if workflow_request.background:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={
                "error": "Not implemented",
                "code": "NOT_IMPLEMENTED",
                "message": "Background execution not yet implemented",
            },
        )

    # Phase 2: Streaming mode (to be implemented)
    if workflow_request.stream:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={
                "error": "Not implemented",
                "code": "NOT_IMPLEMENTED",
                "message": "Streaming execution not yet implemented",
            },
        )

    # Phase 3: Synchronous execution (default)
    # Note: flow is guaranteed to be non-None here because get_flow_by_id_or_endpoint_name
    # raises HTTPException if flow is not found
    try:
        return await execute_sync_workflow_with_timeout(
            workflow_request=workflow_request,
            flow=flow,  # type: ignore[arg-type]
            job_id=job_id,
            api_key_user=api_key_user,
            background_tasks=background_tasks,
        )
    except WorkflowTimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error": "Execution timeout",
                "code": "EXECUTION_TIMEOUT",
                "message": f"Workflow execution exceeded {EXECUTION_TIMEOUT} seconds",
                "job_id": job_id,
                "flow_id": workflow_request.flow_id,
                "timeout_seconds": EXECUTION_TIMEOUT,
            },
        ) from None
    except WorkflowValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Workflow validation error",
                "code": "INVALID_FLOW_DATA",
                "message": str(e),
                "job_id": job_id,
                "flow_id": workflow_request.flow_id,
            },
        ) from e


async def execute_sync_workflow_with_timeout(
    workflow_request: WorkflowExecutionRequest,
    flow: FlowRead,
    job_id: str,
    api_key_user: UserRead,
    background_tasks: BackgroundTasks,
) -> WorkflowExecutionResponse:
    """Execute workflow with timeout protection.

    Args:
        workflow_request: The workflow execution request
        flow: The flow to execute
        job_id: Generated job ID for tracking
        api_key_user: Authenticated user
        background_tasks: FastAPI background tasks

    Returns:
        WorkflowExecutionResponse with complete results

    Raises:
        WorkflowTimeoutError: If execution exceeds timeout
        WorkflowValidationError: If flow validation fails
    """
    try:
        return await asyncio.wait_for(
            execute_sync_workflow(
                workflow_request=workflow_request,
                flow=flow,
                job_id=job_id,
                api_key_user=api_key_user,
                background_tasks=background_tasks,
            ),
            timeout=EXECUTION_TIMEOUT,
        )
    except asyncio.TimeoutError as e:
        msg = f"Execution exceeded {EXECUTION_TIMEOUT} seconds"
        raise WorkflowTimeoutError(msg) from e


async def execute_sync_workflow(
    workflow_request: WorkflowExecutionRequest,
    flow: FlowRead,
    job_id: str,
    api_key_user: UserRead,
    background_tasks: BackgroundTasks,  # noqa: ARG001
) -> WorkflowExecutionResponse:
    """Execute workflow synchronously and return complete results.

    This function implements a two-tier error handling strategy:
        1. System-level errors (validation, graph build): Raised as exceptions
        2. Component execution errors: Returned in response body with HTTP 200

    This approach allows clients to receive partial results even when some
    components fail, which is useful for debugging and incremental processing.

    Execution Flow:
        1. Parse flat inputs into tweaks and session_id
        2. Validate flow data exists
        3. Build graph from flow data with tweaks applied
        4. Identify terminal nodes for execution
        5. Execute graph and collect results
        6. Convert V1 RunResponse to V2 WorkflowExecutionResponse

    Args:
        workflow_request: The workflow execution request with inputs and configuration
        flow: The flow model from database
        job_id: Generated job ID for tracking this execution
        api_key_user: Authenticated user for permission checks
        background_tasks: FastAPI background tasks (unused in sync mode)

    Returns:
        WorkflowExecutionResponse: Complete execution results with outputs and metadata

    Raises:
        WorkflowValidationError: If flow data is None or graph build fails
    """
    # Parse flat inputs structure
    tweaks, session_id = parse_flat_inputs(workflow_request.inputs or {})

    # Validate flow data - this is a system error, not execution error
    if flow.data is None:
        msg = f"Flow {flow.id} has no data. The flow may be corrupted."
        raise WorkflowValidationError(msg)

    # Build graph - system error if this fails
    try:
        flow_id_str = str(flow.id)
        user_id = str(api_key_user.id)
        graph_data = flow.data.copy()
        graph_data = process_tweaks(graph_data, tweaks, stream=False)
        graph = Graph.from_payload(graph_data, flow_id=flow_id_str, user_id=user_id, flow_name=flow.name)
    except Exception as e:
        msg = f"Failed to build graph from flow data: {e!s}"
        raise WorkflowValidationError(msg) from e

    # Get terminal nodes - these are the outputs we want
    terminal_node_ids = graph.get_terminal_nodes()

    # Execute graph - component errors are caught and returned in response body
    try:
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

    except asyncio.CancelledError:
        # Re-raise CancelledError to allow timeout mechanism to work properly
        # This ensures asyncio.wait_for() can properly cancel and raise TimeoutError
        raise
    except Exception as exc:  # noqa: BLE001
        # Component execution errors - return in response body with HTTP 200
        # This allows partial results and detailed error information per component
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
    """Get workflow job status and results by job ID.

    This endpoint allows clients to poll for the status of background workflow executions.

    Args:
        api_key_user: Authenticated user from API key
        job_id: The job ID returned from a background execution request

    Returns:
        - WorkflowExecutionResponse: If job is complete or failed
        - StreamingResponse: If job is still running (for streaming mode)

    Raises:
        HTTPException:
            - 403: Developer API disabled or unauthorized
            - 404: Job ID not found
            - 501: Not yet implemented

    Note:
        This endpoint is not yet implemented. It will be added in a future release
        to support background and streaming execution modes.
    """
    # TODO: Implement job status tracking and retrieval
    # - Store job metadata in database or cache
    # - Track execution progress and status
    # - Return appropriate response based on job state
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

    This endpoint allows clients to gracefully or forcefully stop a running workflow.

    Args:
        request: Stop request containing job_id and optional force flag
        api_key_user: Authenticated user from API key

    Returns:
        WorkflowStopResponse: Confirmation of stop request with final job status

    Raises:
        HTTPException:
            - 403: Developer API disabled or unauthorized
            - 404: Job ID not found
            - 409: Job already completed or cannot be stopped
            - 501: Not yet implemented

    Note:
        This endpoint is not yet implemented. It will be added in a future release
        to support graceful cancellation of background and streaming executions.

        Planned behavior:
        - force=False: Graceful shutdown (complete current component)
        - force=True: Immediate termination
    """
    # TODO: Implement workflow cancellation
    # - Locate running job by job_id
    # - Send cancellation signal to execution engine
    # - Handle graceful vs forced termination
    # - Update job status and return response
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented /stop yet")
