"""V2 API endpoints for running flows with simplified responses."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated

import sqlalchemy as sa
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from lfx.graph.graph.base import Graph
from lfx.schema.schema import INPUT_FIELD_NAME

from langflow.api.utils import extract_global_variables_from_headers
from langflow.api.v1.endpoints import validate_input_and_tweaks
from langflow.api.v1.schemas import SimplifiedAPIRequest
from langflow.exceptions.api import APIException, InvalidChatInputError
from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.processing.process import process_tweaks
from langflow.services.auth.utils import api_key_security
from langflow.services.database.models.flow.model import Flow, FlowRead
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import get_settings_service, get_telemetry_service
from langflow.services.telemetry.schema import RunPayload

if TYPE_CHECKING:
    from langflow.events.event_manager import EventManager

router = APIRouter(tags=["Run"])


def _prepare_graph(
    flow: Flow, input_request: SimplifiedAPIRequest, user_id: str | None, context: dict | None, *, stream: bool
) -> Graph:
    """Prepare and build the graph from flow data."""
    flow_id_str = str(flow.id)
    if flow.data is None:
        msg = f"Flow {flow_id_str} has no data"
        raise ValueError(msg)

    graph_data = flow.data.copy()
    graph_data = process_tweaks(graph_data, input_request.tweaks or {}, stream=stream)

    return Graph.from_payload(
        graph_data, flow_id=flow_id_str, user_id=str(user_id) if user_id else None, flow_name=flow.name, context=context
    )


def _prepare_inputs(input_request: SimplifiedAPIRequest) -> dict:
    """Prepare input dictionary from request."""
    if input_request.input_value is not None:
        return {INPUT_FIELD_NAME: input_request.input_value}
    return {}


def _prepare_outputs(graph: Graph, input_request: SimplifiedAPIRequest) -> list[str]:
    """Prepare output component IDs."""
    if input_request.output_component:
        return [input_request.output_component]
    return [vertex.id for vertex in graph.vertices if vertex.is_output]


def _try_extract_api_response_json(result: list) -> dict | None:
    """Try to extract clean JSON from API Response component."""
    if not result:
        return None

    for output_data in result:
        if not output_data or not hasattr(output_data, "results"):
            continue

        results = output_data.results
        if not isinstance(results, dict):
            continue

        for value in results.values():
            if not hasattr(value, "text"):
                continue

            try:
                parsed_json = json.loads(value.text)
                if isinstance(parsed_json, dict) and "output" in parsed_json and "metadata" in parsed_json:
                    return parsed_json
            except (json.JSONDecodeError, AttributeError):
                continue

    return None


def _extract_output_data(result: list) -> dict:
    """Extract the first meaningful output from results."""
    if not result:
        return {"message": "No output generated"}

    for output in result:
        if not output or not hasattr(output, "results"):
            continue

        results = output.results
        if not isinstance(results, dict) or not results:
            continue

        for value in results.values():
            if hasattr(value, "text"):
                return {"text": value.text}
            if hasattr(value, "data"):
                return {"data": value.data}
            return {"value": str(value)}

    return {"message": "No output generated"}


def _build_response(flow_id: str, output_data: dict, duration_ms: int) -> dict:
    """Build the final response structure."""
    return {
        "output": output_data,
        "metadata": {
            "flow_id": flow_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_ms": duration_ms,
            "status": "complete",
            "error": False,
        },
    }


async def simple_workflow_flow(
    flow: Flow,
    input_request: SimplifiedAPIRequest,
    *,
    stream: bool = False,
    api_key_user: User | None = None,
    event_manager: EventManager | None = None,
    context: dict | None = None,
):
    """Execute a flow and return clean JSON without RunResponse wrapper."""
    validate_input_and_tweaks(input_request)
    start_time = time.time()

    try:
        user_id = api_key_user.id if api_key_user else None
        flow_id_str = str(flow.id)

        # Build graph
        graph = _prepare_graph(flow, input_request, user_id, context, stream=stream)

        # Prepare inputs and outputs
        inputs_dict = _prepare_inputs(input_request)
        outputs = _prepare_outputs(graph, input_request)

        # Run the graph
        effective_session_id = input_request.session_id or flow_id_str
        fallback_to_env_vars = get_settings_service().settings.fallback_to_env_var
        graph.session_id = effective_session_id

        result = await graph.arun_single(
            inputs=inputs_dict,
            input_components=[],
            input_type=input_request.input_type,
            outputs=outputs,
            stream=stream,
            session_id=effective_session_id,
            fallback_to_env_vars=fallback_to_env_vars,
            event_manager=event_manager,
        )

        # Try to extract API Response JSON first
        api_response_json = _try_extract_api_response_json(result)
        if api_response_json:
            return api_response_json

        # Fallback: build minimal response
        duration_ms = int((time.time() - start_time) * 1000)
        output_data = _extract_output_data(result)
        return _build_response(flow_id_str, output_data, duration_ms)

    except sa.exc.StatementError as exc:
        raise ValueError(str(exc)) from exc


@router.post("/run/stateless/{flow_id_or_name}", response_model=None, response_model_exclude_none=True)
async def workflow_run_flow(
    *,
    background_tasks: BackgroundTasks,
    flow: Annotated[FlowRead | None, Depends(get_flow_by_id_or_endpoint_name)],
    inputs: dict | None = None,
    api_key_user: Annotated[UserRead, Depends(api_key_security)],
    context: dict | None = None,
    http_request: Request,
):
    """Executes a flow in stateless mode and returns clean JSON without verbose wrapping.

    This endpoint is optimized for workflow automation and provides clean, minimal
    JSON responses without the verbose RunResponse wrapper. It automatically detects
    API Response components and returns their clean JSON structure directly.

    **Stateless Execution:**
    This endpoint runs in stateless mode, which means:
    - Message history is NOT persisted to the database
    - Chat memory components will work but messages won't be saved
    - Flow execution, transactions, and vertex builds are still tracked
    - load_from_db_fields will still work for global variables

    This makes the endpoint ideal for production stateless execution where
    you don't need persistent chat history.

    Request Body:
        {
            "inputs": dict (optional) - Component-specific inputs/parameters to pass to the flow
        }

    Args:
        background_tasks (BackgroundTasks): FastAPI background task manager
        flow (FlowRead | None): The flow to execute, loaded via dependency
        inputs (dict | None): Component-specific inputs/parameters to pass to the flow
        api_key_user (UserRead): Authenticated user from API key
        context (dict | None): Optional context to pass to the flow
        http_request (Request): The incoming HTTP request for extracting global variables

    Returns:
        dict: Clean JSON response with minimal structure:
            - output: The actual data from the flow
            - metadata: Essential metadata (flow_id, timestamp, duration, status)

    Raises:
        HTTPException: For flow not found (404) or invalid input (400)
        APIException: For internal execution errors (500)

    Notes:
        - Optimized for API Response components - returns their clean JSON directly
        - For other components, creates a minimal response structure
        - Does not include session_id or verbose metadata like the /run endpoint
        - Streaming is not supported
        - Extracts global variables from HTTP headers with prefix X-LANGFLOW-GLOBAL-VAR-*
        - Stateless mode: Messages are NOT persisted to the database
    """
    telemetry_service = get_telemetry_service()

    if flow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")

    # Initialize context with stateless flag for this endpoint
    context = {} if context is None else context.copy()  # Don't modify the original context

    # Set stateless mode - this endpoint doesn't persist message history
    context["stateless"] = True

    # Extract request-level variables from headers with prefix X-LANGFLOW-GLOBAL-VAR-*
    request_variables = extract_global_variables_from_headers(http_request.headers)
    if request_variables:
        context["request_variables"] = request_variables

    # Create a minimal input request object for compatibility with existing helper functions
    input_request = SimplifiedAPIRequest(tweaks=inputs or {})

    start_time = time.perf_counter()

    try:
        result = await simple_workflow_flow(
            flow=flow, input_request=input_request, stream=False, api_key_user=api_key_user, context=context
        )
        end_time = time.perf_counter()
        background_tasks.add_task(
            telemetry_service.log_package_run,
            RunPayload(
                run_is_webhook=False,
                run_seconds=int(end_time - start_time),
                run_success=True,
                run_error_message="",
            ),
        )

    except ValueError as exc:
        background_tasks.add_task(
            telemetry_service.log_package_run,
            RunPayload(
                run_is_webhook=False,
                run_seconds=int(time.perf_counter() - start_time),
                run_success=False,
                run_error_message=str(exc),
            ),
        )
        if "badly formed hexadecimal UUID string" in str(exc):
            # This means the Flow ID is not a valid UUID which means it can't find the flow
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if "not found" in str(exc):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise APIException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, exception=exc, flow=flow) from exc
    except InvalidChatInputError as exc:
        background_tasks.add_task(
            telemetry_service.log_package_run,
            RunPayload(
                run_is_webhook=False,
                run_seconds=int(time.perf_counter() - start_time),
                run_success=False,
                run_error_message=str(exc),
            ),
        )
        raise APIException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, exception=exc, flow=flow) from exc

    return result
