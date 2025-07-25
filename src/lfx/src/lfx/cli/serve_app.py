"""FastAPI application factory for serving LFX flows."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader, APIKeyQuery
from loguru import logger
from pydantic import BaseModel, Field

from lfx.cli.common import execute_graph_with_capture, extract_result_data, get_api_key

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from lfx.graph import Graph

# Security - use the same pattern as Langflow main API
API_KEY_NAME = "x-api-key"
api_key_query = APIKeyQuery(name=API_KEY_NAME, scheme_name="API key query", auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_NAME, scheme_name="API key header", auto_error=False)


def verify_api_key(
    query_param: Annotated[str | None, Security(api_key_query)],
    header_param: Annotated[str | None, Security(api_key_header)],
) -> str:
    """Verify API key from query parameter or header."""
    provided_key = query_param or header_param
    if not provided_key:
        raise HTTPException(status_code=401, detail="API key required")

    try:
        expected_key = get_api_key()
        if provided_key != expected_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return provided_key


class FlowMeta(BaseModel):
    """Metadata for a flow."""

    id: str = Field(..., description="Flow identifier")
    relative_path: str = Field(..., description="Path of the flow JSON relative to the deployed folder")
    title: str = Field(..., description="Human-readable title")
    description: str | None = Field(None, description="Optional flow description")


class RunRequest(BaseModel):
    """Request model for executing a flow."""

    input_value: str = Field(..., description="Input value passed to the flow")


class RunResponse(BaseModel):
    """Response model for flow execution."""

    result: str = Field(..., description="The output result from the flow execution")
    success: bool = Field(..., description="Whether execution was successful")
    logs: str = Field("", description="Captured logs from execution")
    type: str = Field("message", description="Type of result")
    component: str = Field("", description="Component that generated the result")


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error message")
    success: bool = Field(default=False, description="Always false for errors")


def create_serve_app(
    *,
    root_dir: Path,  # noqa: ARG001
    graphs: dict[str, Graph],
    metas: dict[str, FlowMeta],
    verbose_print: Callable[[str], None],  # noqa: ARG001
) -> FastAPI:
    """Create a FastAPI app for serving LFX flows.

    Parameters
    ----------
    root_dir
        Folder originally supplied to the serve command.
    graphs
        Mapping flow_id -> Graph containing prepared graph objects.
    metas
        Mapping flow_id -> FlowMeta containing metadata for each flow.
    verbose_print
        Diagnostic printer inherited from the CLI.
    """
    if set(graphs) != set(metas):
        msg = "graphs and metas must contain the same keys"
        raise ValueError(msg)

    # Determine if we're serving a single flow or multiple flows
    is_single_flow = len(graphs) == 1
    single_flow_id = next(iter(graphs)) if is_single_flow else None

    app = FastAPI(
        title=f"LFX Flow Server{' - ' + metas[single_flow_id].title if is_single_flow else ''}",
        description=(
            f"This server hosts {'the' if is_single_flow else 'multiple'} LFX flow{'s' if not is_single_flow else ''}. "
            f"{'Use POST /run to execute the flow.' if is_single_flow else 'Use /flows to list available flows.'}"
        ),
        version="1.0.0",
    )

    # ------------------------------------------------------------------
    # Global endpoints
    # ------------------------------------------------------------------

    if not is_single_flow:

        @app.get("/flows", response_model=list[FlowMeta], tags=["info"], summary="List available flows")
        async def list_flows():
            """Return metadata for all flows hosted in this server."""
            return list(metas.values())

    @app.get("/health", tags=["info"], summary="Health check")
    async def health():
        return {"status": "healthy", "flow_count": len(graphs)}

    # ------------------------------------------------------------------
    # Flow execution endpoints
    # ------------------------------------------------------------------

    def create_flow_router(flow_id: str, graph: Graph, meta: FlowMeta) -> APIRouter:
        """Create a router for a specific flow."""
        router = APIRouter(
            prefix=f"/flows/{flow_id}" if not is_single_flow else "",
            tags=[meta.title or flow_id],
            dependencies=[Depends(verify_api_key)],  # Auth for all routes
        )

        @router.post(
            "/run",
            response_model=RunResponse,
            responses={500: {"model": ErrorResponse}},
            summary="Execute flow",
            description=f"Execute the {'deployed' if is_single_flow else meta.title or flow_id} flow.",
        )
        async def run_flow(
            request: RunRequest,
        ) -> RunResponse:
            try:
                graph_copy = deepcopy(graph)
                results, logs = await execute_graph_with_capture(graph_copy, request.input_value)
                result_data = extract_result_data(results, logs)

                # Debug logging
                logger.debug(f"Flow {flow_id} execution completed: {len(results)} results, {len(logs)} log chars")
                logger.debug(f"Flow {flow_id} result data: {result_data}")

                # Check if the execution was successful
                if not result_data.get("success", True):
                    # If the flow execution failed, return error details in the response
                    error_message = result_data.get("result", result_data.get("text", "No response generated"))

                    # Add more context to the logs when there's an error
                    error_logs = logs
                    if not error_logs.strip():
                        error_logs = (
                            f"Flow execution completed but no valid result was produced.\nResult data: {result_data}"
                        )

                    return RunResponse(
                        result=error_message,
                        success=False,
                        logs=error_logs,
                        type="error",
                        component=result_data.get("component", ""),
                    )

                return RunResponse(
                    result=result_data.get("result", result_data.get("text", "")),
                    success=result_data.get("success", True),
                    logs=logs,
                    type=result_data.get("type", "message"),
                    component=result_data.get("component", ""),
                )
            except Exception as exc:  # noqa: BLE001
                import traceback

                # Capture the full traceback for debugging
                error_traceback = traceback.format_exc()
                error_message = f"Flow execution failed: {exc!s}"

                # Log to server console for debugging
                logger.error(f"Error running flow {flow_id}: {exc}")
                logger.debug(f"Full traceback for flow {flow_id}:\n{error_traceback}")

                # Return error details in the API response instead of raising HTTPException
                return RunResponse(
                    result=error_message,
                    success=False,
                    logs=f"ERROR: {error_message}\n\nFull traceback:\n{error_traceback}",
                    type="error",
                    component="",
                )

        if not is_single_flow:

            @router.get("/info", summary="Flow metadata", response_model=FlowMeta)
            async def flow_info():
                """Return metadata for this flow."""
                return meta

        return router

    # Include routers for each flow
    for flow_id, graph in graphs.items():
        meta = metas[flow_id]
        router = create_flow_router(flow_id, graph, meta)
        app.include_router(router)

    return app
