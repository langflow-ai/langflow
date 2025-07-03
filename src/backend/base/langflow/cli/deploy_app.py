from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from langflow.cli.commands import verify_api_key
from langflow.cli.common import execute_graph_with_capture, extract_result_data
from langflow.graph import Graph


class RunRequest(BaseModel):
    input_value: str = Field(..., description="Input value to pass to the graph")


class RunResponse(BaseModel):
    result: str = Field(..., description="The output result from the graph")
    success: bool = Field(..., description="Whether the execution was successful")
    logs: str = Field(default="", description="Captured logs from execution")
    type: str = Field(default="message", description="Type of the result")
    component: str = Field(default="", description="Component that generated the result")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    success: bool = Field(default=False, description="Whether the execution was successful")


def create_deploy_app(
    graph: Graph,
    script_path: str,
    resolved_path,
    verbose_print: Callable[[str], None],
) -> FastAPI:
    """Create and configure the FastAPI app for deployment."""
    app = FastAPI(
        title="Langflow Graph Deployment",
        description=f"Authenticated API for the deployed graph from {resolved_path.name}",
        version="1.0.0",
    )

    @app.post("/run", response_model=RunResponse, responses={500: {"model": ErrorResponse}})
    async def run_graph_endpoint(request: RunRequest, _api_key: Annotated[str, Depends(verify_api_key)]):
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

    @app.get("/")
    async def root():
        return {
            "message": "Langflow Graph Deployment API",
            "graph_file": str(resolved_path.name),
            "graph_source": script_path if script_path != str(resolved_path) else "local file",
            "endpoints": {"run": "/run (POST)", "health": "/health (GET)"},
            "authentication": "x-api-key header or query parameter required",
        }

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "graph_ready": True}

    return app
