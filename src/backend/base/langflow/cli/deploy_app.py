from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from langflow.cli.common import execute_graph_with_capture, extract_result_data

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from langflow.graph import Graph

"""FastAPI application factory for deploying **multiple** Langflow graphs at once.

This module is used by the CLI *deploy* command when the provided path is a
folder containing multiple ``*.json`` flow files.  Each flow is exposed under
its own router prefix::

    /flows/{flow_id}/run  - POST - execute the flow
    /flows/{flow_id}/info - GET  - metadata

A global ``/flows`` endpoint lists all available flows and returns a JSON array
of metadata objects, allowing API consumers to discover IDs without guessing.

Authentication behaves exactly like the single-flow deployment: all execution
endpoints require the ``x-api-key`` header (or query parameter) validated by
:func:`langflow.cli.commands.verify_api_key`.
"""


def _analyze_graph_structure(graph: Graph) -> dict[str, Any]:
    """Analyze the graph structure to extract dynamic documentation information.

    Args:
        graph: The Langflow graph to analyze

    Returns:
        dict: Graph analysis including components, input/output types, and flow details
    """
    analysis = {
        "components": [],
        "input_types": set(),
        "output_types": set(),
        "node_count": 0,
        "edge_count": 0,
        "entry_points": [],
        "exit_points": [],
    }

    try:
        # Analyze nodes
        for node_id, node in graph.nodes.items():
            analysis["node_count"] += 1
            component_info = {
                "id": node_id,
                "type": node.data.get("type", "Unknown"),
                "name": node.data.get("display_name", node.data.get("type", "Unknown")),
                "description": node.data.get("description", ""),
                "template": node.data.get("template", {}),
            }
            analysis["components"].append(component_info)

            # Identify entry points (nodes with no incoming edges)
            if not any(edge.source == node_id for edge in graph.edges):
                analysis["entry_points"].append(component_info)

            # Identify exit points (nodes with no outgoing edges)
            if not any(edge.target == node_id for edge in graph.edges):
                analysis["exit_points"].append(component_info)

        # Analyze edges
        analysis["edge_count"] = len(graph.edges)

        # Try to determine input/output types from entry/exit points
        for entry in analysis["entry_points"]:
            template = entry.get("template", {})
            for field_config in template.values():
                if field_config.get("type") in ["str", "text", "string"]:
                    analysis["input_types"].add("text")
                elif field_config.get("type") in ["int", "float", "number"]:
                    analysis["input_types"].add("numeric")
                elif field_config.get("type") in ["file", "path"]:
                    analysis["input_types"].add("file")

        for exit_point in analysis["exit_points"]:
            template = exit_point.get("template", {})
            for field_config in template.values():
                if field_config.get("type") in ["str", "text", "string"]:
                    analysis["output_types"].add("text")
                elif field_config.get("type") in ["int", "float", "number"]:
                    analysis["output_types"].add("numeric")
                elif field_config.get("type") in ["file", "path"]:
                    analysis["output_types"].add("file")

    except (KeyError, AttributeError):
        # If analysis fails, provide basic info
        analysis["components"] = [{"type": "Unknown", "name": "Graph Component"}]
        analysis["input_types"] = {"text"}
        analysis["output_types"] = {"text"}

    # Convert sets to lists for JSON serialization
    analysis["input_types"] = list(analysis["input_types"])
    analysis["output_types"] = list(analysis["output_types"])

    return analysis


def _generate_dynamic_run_description(graph: Graph) -> str:
    """Generate dynamic description for the /run endpoint based on graph analysis.

    Args:
        graph: The Langflow graph

    Returns:
        str: Dynamic description for the /run endpoint
    """
    analysis = _analyze_graph_structure(graph)

    # Determine input examples based on entry points
    input_examples = []
    for entry in analysis["entry_points"]:
        template = entry.get("template", {})
        for field_name, field_config in template.items():
            if field_config.get("type") in ["str", "text", "string"]:
                input_examples.append(f'"{field_name}": "Your input text here"')
            elif field_config.get("type") in ["int", "float", "number"]:
                input_examples.append(f'"{field_name}": 42')
            elif field_config.get("type") in ["file", "path"]:
                input_examples.append(f'"{field_name}": "/path/to/file.txt"')

    if not input_examples:
        input_examples = ['"input_value": "Your input text here"']

    # Determine output examples based on exit points
    output_examples = []
    for exit_point in analysis["exit_points"]:
        template = exit_point.get("template", {})
        for field_name, field_config in template.items():
            if field_config.get("type") in ["str", "text", "string"]:
                output_examples.append(f'"{field_name}": "Processed result"')
            elif field_config.get("type") in ["int", "float", "number"]:
                output_examples.append(f'"{field_name}": 123')
            elif field_config.get("type") in ["file", "path"]:
                output_examples.append(f'"{field_name}": "/path/to/output.txt"')

    if not output_examples:
        output_examples = ['"result": "Processed result"']

    description_parts = [
        f"Execute the deployed Langflow graph with {analysis['node_count']} components.",
        "",
        "**Graph Analysis**:",
        f"- Entry points: {len(analysis['entry_points'])}",
        f"- Exit points: {len(analysis['exit_points'])}",
        f"- Input types: {', '.join(analysis['input_types']) if analysis['input_types'] else 'text'}",
        f"- Output types: {', '.join(analysis['output_types']) if analysis['output_types'] else 'text'}",
        "",
        "**Authentication Required**: Include your API key in the `x-api-key` header or as a query parameter.",
        "",
        "**Example Request**:",
        "```json",
        "{",
        f"  {', '.join(input_examples)}",
        "}",
        "```",
        "",
        "**Example Response**:",
        "```json",
        "{",
        f"  {', '.join(output_examples)},",
        '  "success": true,',
        '  "logs": "Graph execution completed successfully",',
        '  "type": "message",',
        '  "component": "FinalComponent"',
        "}",
        "```",
    ]

    return "\n".join(description_parts)


class FlowMeta(BaseModel):
    """Metadata returned by the ``/flows`` endpoint."""

    id: str = Field(..., description="Deterministic flow identifier (UUIDv5)")
    relative_path: str = Field(..., description="Path of the flow JSON relative to the deployed folder")
    title: str = Field(..., description="Human-readable title (filename stem if unknown)")
    description: str | None = Field(None, description="Optional flow description")


class RunRequest(BaseModel):
    """Request model for executing a Langflow flow."""

    input_value: str = Field(..., description="Input value passed to the flow")


class RunResponse(BaseModel):
    """Response model mirroring the single-flow deployment."""

    result: str = Field(..., description="The output result from the flow execution")
    success: bool = Field(..., description="Whether execution was successful")
    logs: str = Field("", description="Captured logs from execution")
    type: str = Field("message", description="Type of result")
    component: str = Field("", description="Component that generated the result")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    success: bool = Field(default=False, description="Always false for errors")


# -----------------------------------------------------------------------------
# Application factory
# -----------------------------------------------------------------------------


def create_multi_deploy_app(
    *,
    root_dir: Path,  # noqa: ARG001
    graphs: dict[str, Graph],
    metas: dict[str, FlowMeta],
    verbose_print: Callable[[str], None],
) -> FastAPI:
    """Create a FastAPI app exposing multiple Langflow flows.

    Parameters
    ----------
    root_dir
        Folder originally supplied to the deploy command.  All *relative_path*
        values are relative to this directory.
    graphs
        Mapping ``flow_id -> Graph`` containing prepared graph objects.
    metas
        Mapping ``flow_id -> FlowMeta`` containing metadata for each flow.
    verbose_print
        Diagnostic printer inherited from the CLI.
    """
    # Import here to avoid circular import
    from langflow.cli.commands import verify_api_key

    if set(graphs) != set(metas):  # pragma: no cover - sanity check
        msg = "graphs and metas must contain the same keys"
        raise ValueError(msg)

    app = FastAPI(
        title=f"Langflow Multi-Flow Deployment ({len(graphs)})",
        description=(
            "This deployment hosts multiple Langflow graphs under the `/flows/{id}` prefix. "
            "Use `/flows` to list available IDs then POST your input to `/flows/{id}/run`."
        ),
        version="1.0.0",
    )

    # ------------------------------------------------------------------
    # Global endpoints
    # ------------------------------------------------------------------

    @app.get("/flows", response_model=list[FlowMeta], tags=["info"], summary="List available flows")
    async def list_flows():
        """Return metadata for all flows hosted in this deployment."""
        return list(metas.values())

    @app.get("/health", tags=["info"], summary="Global health check")
    async def global_health():
        return {"status": "healthy", "flow_count": len(graphs)}

    # ------------------------------------------------------------------
    # Per-flow routers
    # ------------------------------------------------------------------

    def create_flow_router(flow_id: str, graph: Graph, meta: FlowMeta) -> APIRouter:
        """Create a router for a specific flow to avoid loop variable binding issues."""
        analysis = _analyze_graph_structure(graph)
        run_description = _generate_dynamic_run_description(graph)

        router = APIRouter(
            prefix=f"/flows/{flow_id}",
            tags=[meta.title or flow_id],
            dependencies=[Depends(verify_api_key)],  # Auth for all routes inside
        )

        @router.post(
            "/run",
            response_model=RunResponse,
            responses={500: {"model": ErrorResponse}},
            summary="Execute flow",
            description=run_description,
        )
        async def run_flow(
            request: RunRequest,
            _api_key: Annotated[str, Depends(verify_api_key)],
        ) -> RunResponse:
            try:
                results, logs = execute_graph_with_capture(graph, request.input_value)
                result_data = extract_result_data(results, logs)
                return RunResponse(
                    result=result_data.get("result", result_data.get("text", "")),
                    success=result_data.get("success", True),
                    logs=logs,
                    type=result_data.get("type", "message"),
                    component=result_data.get("component", ""),
                )
            except Exception as exc:
                verbose_print(f"Error running flow {flow_id}: {exc}")
                raise HTTPException(status_code=500, detail=str(exc)) from exc

        @router.get("/info", summary="Flow metadata", response_model=FlowMeta)
        async def flow_info():
            """Return metadata and basic analysis for this flow."""
            # Enrich meta with analysis data for convenience
            return {
                **meta.dict(),
                "components": analysis["node_count"],
                "connections": analysis["edge_count"],
                "input_types": analysis["input_types"],
                "output_types": analysis["output_types"],
            }

        return router

    for flow_id, graph in graphs.items():
        meta = metas[flow_id]
        router = create_flow_router(flow_id, graph, meta)
        app.include_router(router)

    return app
