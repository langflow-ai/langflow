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
from copy import deepcopy
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from lfx.graph.graph.base import Graph
from lfx.schema.workflow import (
    WORKFLOW_EXECUTION_RESPONSES,
    WORKFLOW_STATUS_RESPONSES,
    JobStatus,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowJobResponse,
    WorkflowStopRequest,
    WorkflowStopResponse,
)
from lfx.services.deps import get_settings_service
from pydantic_core import ValidationError as PydanticValidationError
from sqlalchemy.exc import OperationalError

from langflow.api.utils import extract_global_variables_from_headers
from langflow.api.v1.schemas import RunResponse
from langflow.api.v2.converters import (
    create_error_response,
    parse_flat_inputs,
    run_response_to_workflow_response,
)
from langflow.exceptions.api import (
    WorkflowQueueFullError,
    WorkflowResourceError,
    WorkflowServiceUnavailableError,
    WorkflowTimeoutError,
    WorkflowValidationError,
)
from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.processing.process import process_tweaks, run_graph_internal
from langflow.services.auth.utils import api_key_security
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import get_task_service

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


router = APIRouter(prefix="/workflows", tags=["Workflow"], dependencies=[Depends(check_developer_api_enabled)])


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
    http_request: Request,
    api_key_user: Annotated[UserRead, Depends(api_key_security)],
) -> WorkflowExecutionResponse | WorkflowJobResponse | StreamingResponse:
    """Execute a workflow with support for multiple execution modes.

    **background** and **stream** can't be true at the same time.
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
        http_request: The HTTP request object for extracting headers
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
    job_id = str(uuid4())

    try:
        # Validate flow exists and user has permission
        flow = await get_flow_by_id_or_endpoint_name(workflow_request.flow_id, api_key_user.id)

        # Background mode execution
        if workflow_request.background:
            return await execute_workflow_background(
                workflow_request=workflow_request, flow=flow, api_key_user=api_key_user, http_request=http_request
            )

        # Streaming mode (to be implemented)
        if workflow_request.stream:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail={
                    "error": "Not implemented",
                    "code": "NOT_IMPLEMENTED",
                    "message": "Streaming execution not yet implemented",
                },
            )

        # Synchronous execution (default)
        return await execute_sync_workflow_with_timeout(
            workflow_request=workflow_request,
            flow=flow,
            job_id=job_id,
            api_key_user=api_key_user,
            background_tasks=background_tasks,
            http_request=http_request,
        )

    except HTTPException as e:
        # Reformat 404 from get_flow_by_id_or_endpoint_name to structured format
        if e.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Flow not found",
                    "code": "FLOW_NOT_FOUND",
                    "message": f"Flow '{workflow_request.flow_id}' does not exist. Verify the flow_id and try again.",
                    "flow_id": workflow_request.flow_id,
                },
            ) from e
        raise
    except OperationalError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Service unavailable, Please try again.",
                "code": "DATABASE_ERROR",
                "message": f"Failed to fetch flow: {e!s}",
                "flow_id": workflow_request.flow_id,
            },
        ) from e
    except WorkflowTimeoutError:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail={
                "error": "Execution timeout",
                "code": "EXECUTION_TIMEOUT",
                "message": f"Workflow execution exceeded {EXECUTION_TIMEOUT} seconds",
                "job_id": job_id,
                "flow_id": workflow_request.flow_id,
                "timeout_seconds": EXECUTION_TIMEOUT,
            },
        ) from None
    except (PydanticValidationError, WorkflowValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Workflow validation error",
                "code": "INVALID_FLOW_DATA",
                "message": str(e),
                "flow_id": workflow_request.flow_id,
            },
        ) from e
    except WorkflowServiceUnavailableError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Service unavailable",
                "code": "QUEUE_SERVICE_UNAVAILABLE",
                "message": str(err),
                "flow_id": workflow_request.flow_id,
            },
        ) from err
    except (WorkflowResourceError, WorkflowQueueFullError, MemoryError) as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Service busy",
                "code": "SERVICE_BUSY",
                "message": "The service is currently unable to handle the request due to resource limits.",
                "flow_id": workflow_request.flow_id,
            },
        ) from err
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_SERVER_ERROR",
                "message": f"An unexpected error occurred: {err!s}",
                "flow_id": workflow_request.flow_id,
            },
        ) from err


async def execute_sync_workflow_with_timeout(
    workflow_request: WorkflowExecutionRequest,
    flow: FlowRead,
    job_id: str,
    api_key_user: UserRead,
    background_tasks: BackgroundTasks,
    http_request: Request,
) -> WorkflowExecutionResponse:
    """Execute workflow with timeout protection.

    Args:
        workflow_request: The workflow execution request
        flow: The flow to execute
        job_id: Generated job ID for tracking
        api_key_user: Authenticated user
        background_tasks: FastAPI background tasks
        http_request: The HTTP request object for extracting headers

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
                http_request=http_request,
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
    http_request: Request,
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
        3. Extract context from HTTP headers
        4. Build graph from flow data with tweaks applied
        5. Identify terminal nodes for execution
        6. Execute graph and collect results
        7. Convert V1 RunResponse to V2 WorkflowExecutionResponse

    Args:
        workflow_request: The workflow execution request with inputs and configuration
        flow: The flow model from database
        job_id: Generated job ID for tracking this execution
        api_key_user: Authenticated user for permission checks
        background_tasks: FastAPI background tasks (unused in sync mode)
        http_request: The HTTP request object for extracting headers

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

    # Extract request-level variables from headers (similar to V1)
    # Headers with prefix X-LANGFLOW-GLOBAL-VAR-* are extracted and made available to components
    request_variables = extract_global_variables_from_headers(http_request.headers)

    # Build context from request variables (similar to V1's _run_flow_internal)
    context = {"request_variables": request_variables} if request_variables else None

    # Build graph - system error if this fails
    try:
        flow_id_str = str(flow.id)
        user_id = str(api_key_user.id)
        # Use deepcopy to prevent mutation of the original flow.data
        # process_tweaks modifies nested dictionaries in-place
        graph_data = deepcopy(flow.data)
        graph_data = process_tweaks(graph_data, tweaks, stream=False)
        # Pass context to graph (similar to V1's simple_run_flow)
        # This allows components to access request metadata via graph.context
        graph = Graph.from_payload(
            graph_data, flow_id=flow_id_str, user_id=user_id, flow_name=flow.name, context=context
        )
        # Set run_id for tracing/logging (similar to V1's simple_run_flow)
        graph.set_run_id(job_id)
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


async def execute_workflow_background(
    workflow_request: WorkflowExecutionRequest, flow: FlowRead, api_key_user: UserRead, http_request: Request
) -> WorkflowJobResponse:
    """Execute workflow in the background and return job ID for the user to track the execution status."""
    try:
        # Parse flat inputs structure
        tweaks, session_id = parse_flat_inputs(workflow_request.inputs or {})

        # Validate flow data
        if flow.data is None:
            msg = f"Flow {flow.id} has no data"
            raise ValueError(msg)

        # Extract request-level variables from headers (similar to V1)
        # Headers with prefix X-LANGFLOW-GLOBAL-VAR-* are extracted and made available to components
        request_variables = extract_global_variables_from_headers(http_request.headers)

        # Build context from request variables (similar to V1's _run_flow_internal)
        context = {"request_variables": request_variables} if request_variables else None

        # Build the graph once
        flow_id_str = str(flow.id)
        user_id = str(api_key_user.id)
        graph_data = deepcopy(flow.data)
        graph_data = process_tweaks(graph_data, tweaks, stream=False)
        graph = Graph.from_payload(
            graph_data, flow_id=flow_id_str, user_id=user_id, flow_name=flow.name, context=context
        )
        job_id = str(uuid4())
        graph.set_run_id(job_id)

        # Get terminal nodes
        terminal_node_ids = graph.get_terminal_nodes()

        # Launch background task
        task_service = get_task_service()
        await task_service.fire_and_forget_task(
            run_graph_internal,
            graph=graph,
            flow_id=flow_id_str,
            session_id=session_id,
            inputs=None,
            outputs=terminal_node_ids,
            stream=False,
        )
        status = JobStatus.QUEUED
        return WorkflowJobResponse(job_id=graph.run_id, flow_id=workflow_request.flow_id, status=status)

    except (WorkflowResourceError, WorkflowServiceUnavailableError, WorkflowQueueFullError):
        # Re-raise infrastructure/resource errors to be handled by the endpoint
        raise
    except MemoryError as exc:
        raise WorkflowResourceError from exc


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
) -> WorkflowJobResponse:
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
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Workflow status not yet available.")


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
