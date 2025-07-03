"""CLI commands for Langflow."""

from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from dotenv import load_dotenv
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader, APIKeyQuery
from rich.console import Console
from rich.panel import Panel

from langflow.cli.common import (
    create_verbose_printer,
    ensure_dependencies_installed,
    extract_script_dependencies,
    get_api_key,
    get_best_access_host,
    get_free_port,
    is_port_in_use,
    load_graph_from_path,
    validate_script_path,
)
from langflow.cli.deploy_app import create_deploy_app
from langflow.logging.logger import configure

# Initialize console
console = Console()

# Constants
API_KEY_MASK_LENGTH = 8

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


def deploy_command(
    script_path: str = typer.Argument(
        ..., help="Path to the Python script (.py) or JSON flow (.json) containing a graph, or URL to a Python script"
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
    install_deps: bool = typer.Option(  # noqa: FBT001
        True,  # noqa: FBT003
        "--install-deps/--no-install-deps",
        help="Automatically install dependencies declared via PEP-723 inline metadata (Python scripts only)",
    ),
) -> None:
    """Deploy a Langflow graph as a web API endpoint with API key authentication.

    This command loads a Python script or JSON flow containing a Langflow graph
    and starts a FastAPI server that exposes the graph via a POST endpoint.
    The server will accept input values and return the graph's output.

    IMPORTANT: You must set the LANGFLOW_API_KEY environment variable before
    deploying. This key will be required for all API requests.

    Args:
        script_path: Path to the Python script (.py) or JSON flow (.json) containing a graph, or URL to a Python script
        host: Host to bind the server to
        port: Port to bind the server to
        verbose: Show diagnostic output and execution details
        env_file: Path to the .env file containing environment variables
        log_level: Logging level for the server
        install_deps: Automatically install dependencies declared via PEP-723 inline metadata (Python scripts only)

    Example usage:
        export LANGFLOW_API_KEY="your-secret-key-here"
        langflow deploy my_flow.py --host 0.0.0.0 --port 8080
        langflow deploy my_flow.json --verbose --log-level info
        langflow deploy my_flow.py --env-file .env --log-level debug
        langflow deploy https://example.com/my_flow.py --verbose

    Once deployed, you can send POST requests to:
        POST http://host:port/run

        Headers:
        x-api-key: your-secret-key-here

        OR Query parameter:
        POST http://host:port/run?x-api-key=your-secret-key-here

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

    # Validate API key is set
    try:
        api_key = get_api_key()
        verbose_print("✓ LANGFLOW_API_KEY is configured")
    except ValueError as e:
        verbose_print(f"✗ {e}")
        verbose_print("Set the LANGFLOW_API_KEY environment variable before deploying.")
        raise typer.Exit(1) from e

    # Validate log level
    valid_log_levels = {"debug", "info", "warning", "error", "critical"}
    if log_level.lower() not in valid_log_levels:
        verbose_print(f"Error: Invalid log level '{log_level}'. Must be one of: {', '.join(sorted(valid_log_levels))}")
        raise typer.Exit(1)

    # Configure logging with the specified level
    verbose_print(f"Configuring logging with level: {log_level}")
    configure(log_level=log_level)

    # Validate input file/URL and get extension and resolved path
    file_extension, resolved_path = validate_script_path(script_path, verbose_print)

    # Install dependencies declared in the script if requested
    if install_deps and file_extension == ".py":
        deps = extract_script_dependencies(resolved_path, verbose_print)
        if deps:
            ensure_dependencies_installed(deps, verbose_print)
        else:
            verbose_print("No inline dependencies declared - skipping installation")

    # Load the graph
    graph = load_graph_from_path(resolved_path, file_extension, verbose_print, verbose=verbose)

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
    deploy_app = create_deploy_app(graph, script_path, resolved_path, verbose_print)

    # Print deployment information
    verbose_print("🚀 Starting deployment server...")

    protocol = "http"
    access_host = get_best_access_host(host)

    # Mask the API key for display
    masked_key = f"{api_key[:API_KEY_MASK_LENGTH]}..." if len(api_key) > API_KEY_MASK_LENGTH else "***"

    console.print()
    console.print(
        Panel.fit(
            f"[bold green]🎯 Graph Deployed Successfully![/bold green]\n\n"
            f"[bold]Graph:[/bold] {resolved_path.name}\n"
            f"[bold]Source:[/bold] {script_path if script_path != str(resolved_path) else 'local file'}\n"
            f"[bold]Server:[/bold] {protocol}://{access_host}:{port}\n"
            f"[bold]API Endpoint:[/bold] POST {protocol}://{access_host}:{port}/run\n"
            f"[bold]API Key:[/bold] {masked_key}\n\n"
            f"[dim]Send POST requests with:\n"
            f"  Header: x-api-key: <your-api-key>\n"
            f"  OR Query: ?x-api-key=<your-api-key>\n"
            f"  Body: {{'input_value': 'your message'}}[/dim]",
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
