"""V2 Workflow execution endpoints."""

from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from lfx.graph.graph.base import Graph
from lfx.graph.schema import RunOutputs
from lfx.log.logger import logger
from lfx.schema.schema import InputValueRequest
from lfx.schema.workflow import (
    WORKFLOW_EXECUTION_RESPONSES,
    WORKFLOW_STATUS_RESPONSES,
    ComponentOutput,
    ErrorDetail,
    JobStatus,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowJobResponse,
    WorkflowStopRequest,
    WorkflowStopResponse,
    WorkflowStreamEvent,
)
from lfx.services.deps import get_settings_service

from langflow.events.event_manager import create_stream_tokens_event_manager
from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.processing.process import process_tweaks, run_graph_internal
from langflow.services.auth.utils import api_key_security
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import get_queue_service
from langflow.services.job_queue.service import JobQueueNotFoundError, JobQueueService


def check_developer_api_enabled() -> None:
    """Check if developer API is enabled, raise HTTPException if not."""
    settings = get_settings_service().settings
    if not settings.developer_api_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This endpoint is not available",
        )


router = APIRouter(prefix="/workflow", tags=["Workflow"], dependencies=[Depends(check_developer_api_enabled)])


def _get_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _extract_global_inputs(inputs: dict[str, Any] | None) -> dict[str, Any]:
    """Extract global inputs from the inputs dictionary."""
    if not inputs:
        return {}
    return inputs.get("global", {})


def _extract_tweaks(inputs: dict[str, Any] | None) -> dict[str, Any]:
    """Extract component-specific tweaks from inputs (everything except 'global')."""
    if not inputs:
        return {}
    return {k: v for k, v in inputs.items() if k != "global"}


def _build_outputs_dict(task_result: list[RunOutputs]) -> dict[str, ComponentOutput]:
    """Convert task results to ComponentOutput dictionary."""
    outputs: dict[str, ComponentOutput] = {}
    for run_output in task_result:
        if run_output.outputs:
            for output in run_output.outputs:
                component_id = getattr(output, "component_id", None) or str(uuid4())
                outputs[component_id] = ComponentOutput(
                    type=getattr(output, "type", "data"),
                    component_id=component_id,
                    status=JobStatus.COMPLETED,
                    content=output.results if hasattr(output, "results") else output,
                    metadata={},
                )
    return outputs


async def _execute_workflow_sync(
    flow: Any,
    workflow_request: WorkflowExecutionRequest,
    user_id: str,
) -> WorkflowExecutionResponse:
    """Execute workflow synchronously and return complete results."""
    job_id = str(uuid4())
    created_timestamp = _get_timestamp()
    errors: list[ErrorDetail] = []
    outputs: dict[str, ComponentOutput] = {}

    try:
        global_inputs = _extract_global_inputs(workflow_request.inputs)
        tweaks = _extract_tweaks(workflow_request.inputs)

        # Build the graph
        flow_id_str = str(flow.id)
        if flow.data is None:
            msg = f"Flow {flow_id_str} has no data"
            raise ValueError(msg)

        graph_data = flow.data.copy()
        graph_data = process_tweaks(graph_data, tweaks, stream=False)
        graph = Graph.from_payload(
            graph_data,
            flow_id=flow_id_str,
            user_id=user_id,
            flow_name=flow.name,
        )
        graph.set_run_id(job_id)

        # Prepare inputs
        inputs_list = None
        if global_inputs.get("input_value"):
            inputs_list = [
                InputValueRequest(
                    components=[],
                    input_value=global_inputs.get("input_value", ""),
                    type=global_inputs.get("input_type", "chat"),
                )
            ]

        # Get output vertices
        output_vertices = [vertex.id for vertex in graph.vertices if vertex.is_output]

        # Run the graph
        task_result, _session_id = await run_graph_internal(
            graph=graph,
            flow_id=flow_id_str,
            session_id=global_inputs.get("session_id"),
            inputs=inputs_list,
            outputs=output_vertices,
            stream=False,
        )

        outputs = _build_outputs_dict(task_result)
        status_result = JobStatus.COMPLETED

    except (ValueError, RuntimeError, KeyError) as e:
        await logger.aexception(f"Error executing workflow: {e}")
        errors.append(ErrorDetail(error=str(e), code="EXECUTION_ERROR"))
        status_result = JobStatus.FAILED

    return WorkflowExecutionResponse(
        flow_id=workflow_request.flow_id,
        job_id=job_id,
        object="response",
        created_timestamp=created_timestamp,
        status=status_result,
        errors=errors,
        inputs=workflow_request.inputs or {},
        outputs=outputs,
        metadata={"session_id": global_inputs.get("session_id", job_id)},
    )


async def _execute_workflow_stream(
    flow: Any,
    workflow_request: WorkflowExecutionRequest,
    user_id: str,
) -> StreamingResponse:
    """Execute workflow with streaming and return SSE response."""
    job_id = str(uuid4())

    async def event_generator():
        """Generate SSE events for streaming workflow execution."""
        try:
            global_inputs = _extract_global_inputs(workflow_request.inputs)
            tweaks = _extract_tweaks(workflow_request.inputs)

            flow_id_str = str(flow.id)
            if flow.data is None:
                msg = f"Flow {flow_id_str} has no data"
                raise ValueError(msg)

            graph_data = flow.data.copy()
            graph_data = process_tweaks(graph_data, tweaks, stream=True)
            graph = Graph.from_payload(
                graph_data,
                flow_id=flow_id_str,
                user_id=user_id,
                flow_name=flow.name,
            )
            graph.set_run_id(job_id)

            # Set up event manager for streaming
            queue: asyncio.Queue = asyncio.Queue()
            event_manager = create_stream_tokens_event_manager(queue=queue)

            inputs_list = None
            if global_inputs.get("input_value"):
                inputs_list = [
                    InputValueRequest(
                        components=[],
                        input_value=global_inputs.get("input_value", ""),
                        type=global_inputs.get("input_type", "chat"),
                    )
                ]

            output_vertices = [vertex.id for vertex in graph.vertices if vertex.is_output]

            # Start execution task
            async def run_flow():
                try:
                    await run_graph_internal(
                        graph=graph,
                        flow_id=flow_id_str,
                        session_id=global_inputs.get("session_id"),
                        inputs=inputs_list,
                        outputs=output_vertices,
                        stream=True,
                        event_manager=event_manager,
                    )
                    event_manager.on_end(data={"status": "completed"})
                except (ValueError, RuntimeError, KeyError) as e:
                    event_manager.on_error(data={"error": str(e)})
                finally:
                    await queue.put((None, None, time.time()))

            task = asyncio.create_task(run_flow())

            # Yield events from queue with timeout to prevent hanging
            while True:
                try:
                    _event_id, value, _put_time = await asyncio.wait_for(queue.get(), timeout=60.0)
                    if value is None:
                        break
                    event = WorkflowStreamEvent(
                        type="event",
                        run_id=job_id,
                        timestamp=int(time.time() * 1000),
                        raw_event={"data": value.decode("utf-8") if isinstance(value, bytes) else value},
                    )
                    yield f"data: {event.model_dump_json()}\n\n"
                except asyncio.TimeoutError:
                    # Timeout waiting for events - emit error and break
                    timeout_event = WorkflowStreamEvent(
                        type="error",
                        run_id=job_id,
                        timestamp=int(time.time() * 1000),
                        raw_event={"error": "Stream timeout - no events received"},
                    )
                    yield f"data: {timeout_event.model_dump_json()}\n\n"
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
                    break
                except asyncio.CancelledError:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
                    break

            # Final event
            final_event = WorkflowStreamEvent(
                type="end",
                run_id=job_id,
                timestamp=int(time.time() * 1000),
                raw_event={"status": "completed"},
            )
            yield f"data: {final_event.model_dump_json()}\n\n"

        except (ValueError, RuntimeError, KeyError) as e:
            error_event = WorkflowStreamEvent(
                type="error",
                run_id=job_id,
                timestamp=int(time.time() * 1000),
                raw_event={"error": str(e)},
            )
            yield f"data: {error_event.model_dump_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _execute_workflow_background(
    flow: Any,
    workflow_request: WorkflowExecutionRequest,
    user_id: str,
    queue_service: JobQueueService,
) -> WorkflowJobResponse:
    """Start workflow execution in background and return job ID."""
    job_id = str(uuid4())
    created_timestamp = _get_timestamp()

    async def background_execution():
        """Execute workflow in background."""
        try:
            global_inputs = _extract_global_inputs(workflow_request.inputs)
            tweaks = _extract_tweaks(workflow_request.inputs)

            flow_id_str = str(flow.id)
            if flow.data is None:
                msg = f"Flow {flow_id_str} has no data"
                raise ValueError(msg)

            graph_data = flow.data.copy()
            graph_data = process_tweaks(graph_data, tweaks, stream=False)
            graph = Graph.from_payload(
                graph_data,
                flow_id=flow_id_str,
                user_id=user_id,
                flow_name=flow.name,
            )
            graph.set_run_id(job_id)

            inputs_list = None
            if global_inputs.get("input_value"):
                inputs_list = [
                    InputValueRequest(
                        components=[],
                        input_value=global_inputs.get("input_value", ""),
                        type=global_inputs.get("input_type", "chat"),
                    )
                ]

            output_vertices = [vertex.id for vertex in graph.vertices if vertex.is_output]

            await run_graph_internal(
                graph=graph,
                flow_id=flow_id_str,
                session_id=global_inputs.get("session_id"),
                inputs=inputs_list,
                outputs=output_vertices,
                stream=False,
            )
            await logger.ainfo(f"Background workflow {job_id} completed successfully")
        except (ValueError, RuntimeError, KeyError) as e:
            await logger.aexception(f"Background workflow {job_id} failed: {e}")
            raise  # Re-raise so task.exception() is set for status detection

    # Create queue for job tracking
    try:
        queue_service.create_queue(job_id)
        queue_service.start_job(job_id, background_execution())
    except (ValueError, RuntimeError) as e:
        await logger.aexception(f"Failed to start background job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start background job: {e}",
        ) from e

    return WorkflowJobResponse(
        job_id=job_id,
        created_timestamp=created_timestamp,
        status=JobStatus.QUEUED,
        errors=[],
    )


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
    api_key_user: Annotated[UserRead, Depends(api_key_security)],
    queue_service: Annotated[JobQueueService, Depends(get_queue_service)],
) -> WorkflowExecutionResponse | WorkflowJobResponse | StreamingResponse:
    """Execute a workflow with multiple execution modes.

    - **sync**: Returns complete results immediately (background=False, stream=False)
    - **stream**: Returns server-sent events in real-time (stream=True)
    - **background**: Starts job and returns job ID immediately (background=True)
    """
    flow = await get_flow_by_id_or_endpoint_name(workflow_request.flow_id, api_key_user.id)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Flow {workflow_request.flow_id} not found")

    user_id = str(api_key_user.id)

    # Validate mutually exclusive execution modes
    if workflow_request.background and workflow_request.stream:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only one execution mode can be selected: either 'background' or 'stream', not both.",
        )

    # Determine execution mode
    if workflow_request.background:
        # Background mode: Start job and return immediately
        return await _execute_workflow_background(
            flow=flow,
            workflow_request=workflow_request,
            user_id=user_id,
            queue_service=queue_service,
        )
    if workflow_request.stream:
        # Streaming mode: Return SSE stream
        return await _execute_workflow_stream(
            flow=flow,
            workflow_request=workflow_request,
            user_id=user_id,
        )
    # Synchronous mode: Execute and return complete results
    return await _execute_workflow_sync(
        flow=flow,
        workflow_request=workflow_request,
        user_id=user_id,
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
    _api_key_user: Annotated[UserRead, Depends(api_key_security)],
    job_id: Annotated[str, Query(description="Job ID to query")],
    queue_service: Annotated[JobQueueService, Depends(get_queue_service)],
) -> WorkflowExecutionResponse:
    """Get workflow job status and results by job ID.

    Returns the current status and any available results for a background workflow job.
    """
    try:
        _main_queue, _event_manager, task, cleanup_timestamp = queue_service.get_queue_data(job_id)

        # Determine job status based on task state
        if task is None:
            job_status = JobStatus.QUEUED
        elif task.done():
            if task.cancelled():
                job_status = JobStatus.FAILED
            elif task.exception():
                job_status = JobStatus.ERROR
            else:
                job_status = JobStatus.COMPLETED
        else:
            job_status = JobStatus.IN_PROGRESS

        errors: list[ErrorDetail] = []
        if task and task.done() and task.exception():
            errors.append(
                ErrorDetail(
                    error=str(task.exception()),
                    code="EXECUTION_ERROR",
                )
            )

        return WorkflowExecutionResponse(
            flow_id="",  # Not stored in queue service
            job_id=job_id,
            object="response",
            created_timestamp=_get_timestamp(),
            status=job_status,
            errors=errors,
            inputs={},
            outputs={},
            metadata={"cleanup_timestamp": cleanup_timestamp},
        )

    except JobQueueNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        ) from e
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e


@router.post(
    "/stop",
    summary="Stop Workflow",
    description="Stop a running workflow execution",
)
async def stop_workflow(
    request: WorkflowStopRequest,
    _api_key_user: Annotated[UserRead, Depends(api_key_security)],
    queue_service: Annotated[JobQueueService, Depends(get_queue_service)],
) -> WorkflowStopResponse:
    """Stop a running workflow execution by job_id.

    Parameters:
    - job_id: The specific job ID to stop
    - force: Whether to force stop the workflow (optional)
    """
    job_id = request.job_id

    try:
        # Check if job exists
        _main_queue, _event_manager, task, _ = queue_service.get_queue_data(job_id)

        if task is None:
            return WorkflowStopResponse(
                job_id=job_id,
                status="not_found",
                message="No active task found for this job",
            )

        if task.done():
            return WorkflowStopResponse(
                job_id=job_id,
                status="stopped",
                message="Job has already completed",
            )

        # Cancel the task
        task.cancel()

        # Await cancellation to ensure cleanup
        with contextlib.suppress(asyncio.CancelledError):
            await task

        if request.force:
            # Force cleanup immediately
            await queue_service.cleanup_job(job_id)
            return WorkflowStopResponse(
                job_id=job_id,
                status="stopped",
                message="Job forcefully stopped and cleaned up",
            )

        return WorkflowStopResponse(
            job_id=job_id,
            status="stopped",
            message="Job stopped successfully",
        )

    except JobQueueNotFoundError:
        return WorkflowStopResponse(
            job_id=job_id,
            status="not_found",
            message=f"Job {job_id} not found",
        )
    except (ValueError, RuntimeError, asyncio.CancelledError) as e:
        await logger.aexception(f"Error stopping workflow {job_id}: {e}")
        return WorkflowStopResponse(
            job_id=job_id,
            status="error",
            message=str(e),
        )
