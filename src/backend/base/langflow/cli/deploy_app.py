from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from langflow.cli.commands import verify_api_key
from langflow.cli.common import execute_graph_with_capture, extract_result_data
from langflow.graph import Graph


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


def _generate_dynamic_description(graph: Graph, script_path: str, resolved_path) -> str:
    """Generate dynamic description based on graph analysis.

    Args:
        graph: The Langflow graph
        script_path: Original script path or URL
        resolved_path: Resolved path object

    Returns:
        str: Dynamic description for the FastAPI app
    """
    analysis = _analyze_graph_structure(graph)
    max_components_to_show = 5

    description_parts = [
        f"# Langflow Graph Deployment: {resolved_path.name}",
        "",
        f"**Source**: {script_path if script_path != str(resolved_path) else 'Local file'}",
        f"**Components**: {analysis['node_count']} nodes, {analysis['edge_count']} connections",
        "",
        "## Graph Structure",
        f"- **Entry Points**: {len(analysis['entry_points'])} components",
        f"- **Exit Points**: {len(analysis['exit_points'])} components",
        f"- **Input Types**: {', '.join(analysis['input_types']) if analysis['input_types'] else 'text'}",
        f"- **Output Types**: {', '.join(analysis['output_types']) if analysis['output_types'] else 'text'}",
        "",
        "## Components",
    ]

    # Add component details (limit to first 5 for readability)
    for _i, comp in enumerate(analysis["components"][:max_components_to_show]):
        description_parts.append(f"- **{comp['name']}** ({comp['type']})")
        if comp.get("description"):
            description_parts.append(f"  - {comp['description']}")

    if len(analysis["components"]) > max_components_to_show:
        description_parts.append(f"- ... and {len(analysis['components']) - max_components_to_show} more components")

    description_parts.extend(
        [
            "",
            "## Authentication",
            "All endpoints except `/` and `/health` require authentication via `x-api-key` header or query parameter.",
            "",
            "## Usage",
            "Send your input to the `/run` endpoint and receive the processed result from the graph execution.",
        ]
    )

    return "\n".join(description_parts)


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


class RunRequest(BaseModel):
    """Request model for executing a Langflow graph.

    This model defines the input structure for the /run endpoint.
    """

    input_value: str = Field(
        ...,
        description="Input value to pass to the graph. This will be used as the starting point for graph execution.",
    )


class RunResponse(BaseModel):
    """Response model for graph execution results.

    This model defines the output structure returned by the /run endpoint.
    """

    result: str = Field(
        ..., description="The output result from the graph execution. Contains the final processed data or response."
    )
    success: bool = Field(
        ..., description="Whether the execution was successful. True if the graph completed without errors."
    )
    logs: str = Field(
        default="", description="Captured logs from execution. Contains debug information and execution traces."
    )
    type: str = Field(
        default="message", description="Type of the result. Common values include 'message', 'text', 'data', etc."
    )
    component: str = Field(
        default="",
        description="Component that generated the result. Identifies the final component in the graph execution.",
    )


class ErrorResponse(BaseModel):
    """Error response model for failed requests.

    This model defines the error structure returned when graph execution fails.
    """

    error: str = Field(..., description="Error message describing what went wrong during execution.")
    success: bool = Field(default=False, description="Always false for error responses, indicating execution failure.")


def create_deploy_app(
    graph: Graph,
    script_path: str,
    resolved_path,
    verbose_print: Callable[[str], None],
) -> FastAPI:
    """Create and configure the FastAPI app for deployment.

    This function creates a FastAPI application with endpoints for running Langflow graphs.
    The app includes authentication via API key and provides endpoints for execution,
    health checks, and basic information.

    Args:
        graph: The compiled Langflow graph to be deployed
        script_path: Original path or URL of the script (for display purposes)
        resolved_path: Resolved path object containing the actual script location
        verbose_print: Function for logging verbose output during execution

    Returns:
        FastAPI: Configured FastAPI application with deployment endpoints

    Example:
        ```python
        app = create_deploy_app(
            graph=my_graph,
            script_path="https://example.com/script.py",
            resolved_path=Path("/tmp/script.py"),
            verbose_print=print
        )
        ```
    """
    # Generate dynamic descriptions
    dynamic_description = _generate_dynamic_description(graph, script_path, resolved_path)
    dynamic_run_description = _generate_dynamic_run_description(graph)
    graph_analysis = _analyze_graph_structure(graph)

    app = FastAPI(
        title=f"Langflow Graph: {resolved_path.name}",
        description=dynamic_description,
        version="1.0.0",
        openapi_tags=[
            {"name": "execution", "description": "Graph execution endpoints"},
            {"name": "info", "description": "Deployment information and health checks"},
        ],
    )

    @app.post(
        "/run",
        response_model=RunResponse,
        responses={500: {"model": ErrorResponse}},
        summary=f"Execute {resolved_path.name} graph",
        description=dynamic_run_description,
        tags=["execution"],
    )
    async def run_graph_endpoint(request: RunRequest, _api_key: Annotated[str, Depends(verify_api_key)]):
        """Execute the deployed graph with the provided input.

        This endpoint processes the input through the entire graph pipeline and returns
        the final result. All intermediate steps and logs are captured for debugging.

        Args:
            request: The RunRequest containing the input value to process
            _api_key: API key for authentication (injected by FastAPI)

        Returns:
            RunResponse: The execution result with metadata

        Raises:
            HTTPException: If graph execution fails (500 status code)
        """
        try:
            results, captured_logs = execute_graph_with_capture(graph, request.input_value)
            result_data = extract_result_data(results, captured_logs)
            return RunResponse(
                result=result_data.get("result", result_data.get("text", "")),
                success=result_data.get("success", True),
                logs=captured_logs,
                type=result_data.get("type", "message"),
                component=result_data.get("component", ""),
            )
        except Exception as e:
            verbose_print(f"Error running graph: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.get(
        "/",
        summary=f"Get {resolved_path.name} deployment information",
        description=f"""
        Get detailed information about the deployed graph '{resolved_path.name}' and available endpoints.

        This endpoint provides comprehensive metadata about the deployment including:
        - Graph structure analysis
        - Component details
        - Available endpoints
        - Authentication requirements

        **No Authentication Required**

        **Graph Analysis**:
        - Components: {graph_analysis["node_count"]} nodes, {graph_analysis["edge_count"]} connections
        - Entry Points: {len(graph_analysis["entry_points"])}
        - Exit Points: {len(graph_analysis["exit_points"])}
        - Input Types: {", ".join(graph_analysis["input_types"]) if graph_analysis["input_types"] else "text"}
        - Output Types: {", ".join(graph_analysis["output_types"]) if graph_analysis["output_types"] else "text"}
        """,
        tags=["info"],
    )
    async def root():
        """Get deployment information and endpoint details.

        Returns:
            dict: Information about the deployment including endpoints and authentication
        """
        return {
            "message": f"Langflow Graph Deployment API: {resolved_path.name}",
            "graph_file": str(resolved_path.name),
            "graph_source": script_path if script_path != str(resolved_path) else "local file",
            "graph_analysis": {
                "components": graph_analysis["node_count"],
                "connections": graph_analysis["edge_count"],
                "entry_points": len(graph_analysis["entry_points"]),
                "exit_points": len(graph_analysis["exit_points"]),
                "input_types": graph_analysis["input_types"],
                "output_types": graph_analysis["output_types"],
            },
            "endpoints": {"run": "/run (POST)", "health": "/health (GET)"},
            "authentication": "x-api-key header or query parameter required",
        }

    @app.get(
        "/health",
        summary="Health check endpoint",
        description="""
        Check the health status of the deployed graph.

        This endpoint verifies that the graph is ready to process requests.
        Useful for load balancers and monitoring systems.

        **No Authentication Required**

        **Example Response**:
        ```json
        {
            "status": "healthy",
            "graph_ready": true
        }
        ```
        """,
        tags=["info"],
    )
    async def health_check():
        """Health check endpoint for monitoring and load balancers.

        Returns:
            dict: Health status indicating if the graph is ready
        """
        return {"status": "healthy", "graph_ready": True}

    return app
