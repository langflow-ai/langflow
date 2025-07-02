"""CLI commands for Langflow."""

from pathlib import Path

import typer
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel

from langflow.cli.common import (
    create_verbose_printer,
    execute_graph_with_capture,
    extract_result_data,
    load_graph_from_path,
    validate_script_path,
)
from langflow.logging.logger import configure

# Initialize console
console = Console()

# Constants
MAX_PORT_NUMBER = 65535
NO_FREE_PORTS_MSG = "No free ports available"


def is_port_in_use(port: int, host: str = "localhost") -> bool:
    """Check if a port is already in use."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
        except OSError:
            return True
        else:
            return False


def get_free_port(starting_port: int = 8000) -> int:
    """Get a free port starting from the given port."""
    import socket

    port = starting_port
    while port < MAX_PORT_NUMBER:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
            except OSError:
                port += 1
            else:
                return port

    raise RuntimeError(NO_FREE_PORTS_MSG)


def get_best_access_host(host: str) -> str:
    """Get the best host address for external access."""
    # Note: 0.0.0.0 and :: are intentionally checked as they bind to all interfaces
    if host in ("0.0.0.0", "::"):  # noqa: S104
        return "localhost"
    return host


def deploy_command(
    script_path: Path = typer.Argument(  # noqa: B008
        ..., help="Path to the Python script (.py) or JSON flow (.json) containing a graph"
    ),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind the server to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind the server to"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show diagnostic output and execution details"),  # noqa: FBT001, FBT003
    env_file: Path | None = typer.Option(
        None,
        "--env-file",
        help="Path to the .env file containing environment variables",
    ),
    log_level: str = typer.Option(
        "warning",
        "--log-level",
        help="Logging level. One of: debug, info, warning, error, critical",
    ),
) -> None:
    """Deploy a Langflow graph as a web API endpoint.

    This command loads a Python script or JSON flow containing a Langflow graph
    and starts a FastAPI server that exposes the graph via a POST endpoint.
    The server will accept input values and return the graph's output.

    Args:
        script_path: Path to the Python script (.py) or JSON flow (.json) containing a graph
        host: Host to bind the server to
        port: Port to bind the server to
        verbose: Show diagnostic output and execution details
        env_file: Path to the .env file containing environment variables
        log_level: Logging level for the server

    Example usage:
        langflow deploy my_flow.py --host 0.0.0.0 --port 8080
        langflow deploy my_flow.json --verbose --log-level info
        langflow deploy my_flow.py --env-file .env --log-level debug

    Once deployed, you can send POST requests to:
        POST http://host:port/run

        With JSON body:
        {"input_value": "Your input message"}
    """
    verbose_print = create_verbose_printer(verbose=verbose)

    # Load environment variables from .env file if provided
    if env_file:
        if not env_file.exists():
            verbose_print(f"Error: Environment file '{env_file}' does not exist.")
            raise typer.Exit(1)

        verbose_print(f"Loading environment variables from: {env_file}")
        load_dotenv(env_file)

    # Validate log level
    valid_log_levels = {"debug", "info", "warning", "error", "critical"}
    if log_level.lower() not in valid_log_levels:
        verbose_print(f"Error: Invalid log level '{log_level}'. Must be one of: {', '.join(sorted(valid_log_levels))}")
        raise typer.Exit(1)

    # Configure logging with the specified level
    verbose_print(f"Configuring logging with level: {log_level}")
    configure(log_level=log_level)

    # Validate input file and get extension
    file_extension = validate_script_path(script_path, verbose_print)

    # Load the graph
    graph = load_graph_from_path(script_path, file_extension, verbose_print, verbose=verbose)

    # Prepare the graph
    verbose_print("Preparing graph for deployment...")
    try:
        graph.prepare()
        verbose_print("✓ Graph prepared successfully")
    except Exception as e:
        verbose_print(f"✗ Failed to prepare graph: {e}")
        raise typer.Exit(1) from e

    # Check if port is in use
    if is_port_in_use(port, host):
        available_port = get_free_port(port)
        if verbose:
            verbose_print(f"Port {port} is in use, using port {available_port} instead")
        port = available_port

    # Create FastAPI app
    deploy_app = FastAPI(
        title="Langflow Graph Deployment",
        description=f"API for the deployed graph from {script_path.name}",
        version="1.0.0",
    )

    # Define request/response models
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

    @deploy_app.post("/run", response_model=RunResponse, responses={500: {"model": ErrorResponse}})
    async def run_graph_endpoint(request: RunRequest):
        """Run the deployed graph with the provided input."""
        try:
            # Execute graph and capture output
            results, captured_logs = execute_graph_with_capture(graph, request.input_value)

            # Extract structured result
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

    @deploy_app.get("/")
    async def root():
        """Root endpoint with deployment information."""
        return {
            "message": "Langflow Graph Deployment API",
            "graph_file": str(script_path.name),
            "endpoints": {"run": "/run (POST)", "health": "/health (GET)"},
        }

    @deploy_app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "graph_ready": True}

    # Print deployment information
    verbose_print("🚀 Starting deployment server...")

    protocol = "http"
    access_host = get_best_access_host(host)

    console.print()
    console.print(
        Panel.fit(
            f"[bold green]🎯 Graph Deployed Successfully![/bold green]\n\n"
            f"[bold]Graph:[/bold] {script_path.name}\n"
            f"[bold]Server:[/bold] {protocol}://{access_host}:{port}\n"
            f"[bold]API Endpoint:[/bold] POST {protocol}://{access_host}:{port}/run\n\n"
            f"[dim]Send POST requests with JSON body: {{'input_value': 'your message'}}[/dim]",
            border_style="green",
            title="🚀 Deployment Ready",
        )
    )
    console.print()

    # Start the server
    try:
        uvicorn.run(
            deploy_app,
            host=host,
            port=port,
            log_level=log_level.lower(),
            access_log=verbose,
        )
    except KeyboardInterrupt:
        verbose_print("\n👋 Deployment server stopped")
        raise typer.Exit(0) from None
    except Exception as e:
        verbose_print(f"✗ Failed to start server: {e}")
        raise typer.Exit(1) from e
