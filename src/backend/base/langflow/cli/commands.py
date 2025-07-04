"""CLI commands for Langflow."""

# Import moved to avoid circular import issues
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
import uvicorn
from dotenv import load_dotenv
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader, APIKeyQuery
from rich.console import Console
from rich.panel import Panel

from langflow.cli.common import (
    create_verbose_printer,
    download_and_extract_repo,
    ensure_dependencies_installed,
    extract_script_dependencies,
    flow_id_from_path,
    get_api_key,
    get_best_access_host,
    get_free_port,
    is_port_in_use,
    is_url,
    load_graph_from_path,
    validate_script_path,
)
from langflow.cli.serve_app import FlowMeta, create_multi_serve_app
from langflow.logging.logger import configure

if TYPE_CHECKING:
    from langflow.graph import Graph

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


def serve_command(
    script_path: str = typer.Argument(
        ...,
        help=(
            "Path to Python script (.py), JSON flow (.json), folder with flows, "
            "GitHub repo URL, or URL to a Python script"
        ),
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
    mcp: bool = typer.Option(  # noqa: FBT001
        False,  # noqa: FBT003
        "--mcp/--no-mcp",
        help="Enable MCP (Model Context Protocol) server mode",
    ),
    mcp_transport: str = typer.Option(
        "sse",
        "--mcp-transport",
        help="MCP transport type. Currently only 'sse' is supported",
    ),
    mcp_name: str = typer.Option(
        "Langflow MCP Server",
        "--mcp-name",
        help="Name for the MCP server",
    ),
) -> None:
    """Serve Langflow graphs as web API endpoints or MCP (Model Context Protocol) server.

    This command supports multiple serving modes:

    1. **Single Flow**: Serve a Python script (.py) or JSON flow (.json)
    2. **Folder**: Serve all *.json flows in a directory under /flows/{id} endpoints
    3. **GitHub Repository**: Serve flows from a GitHub repo (supports private repos with GITHUB_TOKEN)
    4. **Remote Script**: Serve a Python script from a URL

    ## REST API Mode (default):
    All served flows use a unified API structure with /flows/{id} endpoints:
    - Single flows: Use the single flow ID under /flows/{id}/run
    - Multi-flows: Use /flows/{id}/run endpoints for each flow
    - Discovery: /flows endpoint lists all available flows

    IMPORTANT: You must set the LANGFLOW_API_KEY environment variable before
    serving. This key will be required for all API requests.

    ## MCP Mode (--mcp):
    Exposes flows as MCP tools, resources, and prompts for direct LLM integration:
    - **Tools**: Each flow becomes an executable MCP tool
    - **Resources**: Flow metadata and schemas available as MCP resources
    - **Prompts**: Help and troubleshooting guidance via MCP prompts

    For GitHub private repositories, set the GITHUB_TOKEN environment variable.

    Args:
        script_path: Path to Python script (.py), JSON flow (.json), folder with flows,
            GitHub repo URL, or URL to a Python script
        host: Host to bind the server to
        port: Port to bind the server to
        verbose: Show diagnostic output and execution details
        env_file: Path to the .env file containing environment variables
        log_level: Logging level for the server
        install_deps: Automatically install dependencies declared via PEP-723 inline metadata (Python scripts only)
        mcp: Enable MCP (Model Context Protocol) server mode
        mcp_transport: MCP transport type (currently only 'sse' is supported)
        mcp_name: Name for the MCP server

    Example usage:
        # REST API mode (default)
        export LANGFLOW_API_KEY="your-secret-key-here"
        langflow serve my_flow.py --host 0.0.0.0 --port 8080
        langflow serve my_flow.json --verbose --log-level info

        # MCP mode with SSE transport (for LLM clients)
        langflow serve my_flow.py --mcp --mcp-transport sse
        
        # MCP mode with custom port
        langflow serve ./my_flows_folder --mcp --port 8000
        
        # MCP mode with custom server name
        langflow serve my_flow.py --mcp --mcp-name "My Custom AI Tools"

        # Folder serving (multiple flows)
        langflow serve ./my_flows_folder --verbose

        # GitHub repository serving
        export GITHUB_TOKEN="ghp_your_token_here"  # For private repos
        langflow serve https://github.com/user/repo --verbose

    REST API Endpoints:
        GET  http://host:port/flows                  # List all flows
        POST http://host:port/flows/{id}/run         # Execute specific flow
        GET  http://host:port/flows/{id}/info        # Flow metadata
        GET  http://host:port/health                 # Health check

    MCP Resources:
        flow://flows                                 # List all flows
        flow://flows/{id}/info                       # Flow metadata
        flow://flows/{id}/schema                     # Flow input/output schema

    MCP Tools:
        execute_{flow_name}                          # Execute specific flow

    Authentication (REST API only):
        Headers: x-api-key: your-secret-key-here
        OR Query: ?x-api-key=your-secret-key-here

    Request body (REST API):
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

    # Validate MCP options
    if mcp:
        if mcp_transport.lower() != "sse":
            verbose_print(f"Warning: Only SSE transport is currently supported. Using 'sse' instead of '{mcp_transport}'")
            mcp_transport = "sse"
        verbose_print(f"✓ MCP mode enabled with {mcp_transport} transport")
    else:
        # Validate API key only for REST API mode
        try:
            api_key = get_api_key()
            verbose_print("✓ LANGFLOW_API_KEY is configured")
        except ValueError as e:
            verbose_print(f"✗ {e}")
            verbose_print("Set the LANGFLOW_API_KEY environment variable before serving.")
            raise typer.Exit(1) from e

    # Validate log level
    valid_log_levels = {"debug", "info", "warning", "error", "critical"}
    if log_level.lower() not in valid_log_levels:
        verbose_print(f"Error: Invalid log level '{log_level}'. Must be one of: {', '.join(sorted(valid_log_levels))}")
        raise typer.Exit(1)

    # Configure logging with the specified level
    verbose_print(f"Configuring logging with level: {log_level}")
    configure(log_level=log_level)

    # ------------------------------------------------------------------
    # Single-file vs directory detection
    # ------------------------------------------------------------------

    # 1) Remote repository / ZIP URL deployment ---------------------------------
    if isinstance(script_path, str) and is_url(script_path) and not script_path.lower().endswith(".py"):
        try:
            folder_path = download_and_extract_repo(script_path, verbose_print)
        except Exception as exc:
            verbose_print(f"Error downloading repository: {exc}")
            raise typer.Exit(1) from exc

        # Treat extracted folder as local directory (re-use logic below)
        script_path_obj = folder_path
    else:
        script_path_obj = Path(script_path)

    if script_path_obj.exists() and script_path_obj.is_dir():
        # --------------------------------------------------------------
        # Folder deployment - expose all *.json flows under /flows/{id}
        # --------------------------------------------------------------
        folder_path = script_path_obj.resolve()

        if str(folder_path) not in sys.path:
            sys.path.insert(0, str(folder_path))

        json_files: list[Path] = [p for p in folder_path.rglob("*.json") if p.is_file()]
        if not json_files:
            verbose_print("Error: No .json flow files found in the provided folder.")
            raise typer.Exit(1)

        graphs: dict[str, Graph] = {}
        metas: dict[str, FlowMeta] = {}

        for json_file in json_files:
            try:
                graph = load_graph_from_path(json_file, ".json", verbose_print, verbose=verbose)
                flow_id = flow_id_from_path(json_file, folder_path)
                graph.flow_id = flow_id  # annotate graph for reference
                graph.prepare()

                title = json_file.stem
                metas[flow_id] = FlowMeta(
                    id=flow_id,
                    relative_path=str(json_file.relative_to(folder_path)),
                    title=title,
                    description=None,
                )
                graphs[flow_id] = graph
                verbose_print(f"✓ Prepared flow '{title}' (id={flow_id})")
            except Exception as exc:
                verbose_print(f"✗ Failed loading flow '{json_file}': {exc}")
                raise typer.Exit(1) from exc

        # Check port availability
        if is_port_in_use(port, host):
            available_port = get_free_port(port)
            if verbose:
                verbose_print(f"Port {port} is in use, using port {available_port} instead")
            port = available_port

        # Start server in appropriate mode
        if mcp:
            # For MCP mode, we start the regular FastAPI server which includes MCP endpoints
            verbose_print(f"🔧 Starting Langflow with MCP server enabled...")
            
            if mcp_transport != "sse":
                verbose_print(f"Note: Currently only SSE transport is supported for MCP. Using SSE transport.")
                mcp_transport = "sse"
            
            # Create the FastAPI app which includes MCP functionality
            serve_app = create_multi_serve_app(
                root_dir=folder_path,
                graphs=graphs,
                metas=metas,
                verbose_print=verbose_print,
            )
            
            protocol = "http"
            access_host = get_best_access_host(host)
            
            console.print()
            console.print(
                Panel.fit(
                    f"[bold green]🎯 MCP Server Started![/bold green]\n\n"
                    f"[bold]Mode:[/bold] MCP (SSE)\n"
                    f"[bold]Folder:[/bold] {folder_path}\n"
                    f"[bold]Flows Detected:[/bold] {len(graphs)}\n"
                    f"[bold]Server:[/bold] {protocol}://{access_host}:{port}\n\n"
                    f"[dim]MCP SSE endpoint:[/dim]\n"
                    f"[blue]{protocol}://{access_host}:{port}/api/v1/mcp/sse[/blue]\n\n"
                    f"[dim]Available MCP Resources:\n"
                    f"  {protocol}://{access_host}:{port}/api/v1/files/{{flow_id}}/{{filename}}\n\n"
                    f"MCP Tools: Each flow becomes an executable tool\n"
                    f"MCP Resources: Flow files accessible via resources\n"
                    f"Note: Flows are automatically available as MCP tools[/dim]",
                    border_style="blue",
                    title="🔧 MCP Server Ready",
                )
            )
            console.print()
            
            try:
                uvicorn.run(
                    serve_app,
                    host=host,
                    port=port,
                    log_level=log_level.lower(),
                    access_log=verbose,
                )
            except KeyboardInterrupt:
                verbose_print("\n👋 MCP server stopped")
                raise typer.Exit(0) from None
            except Exception as e:
                verbose_print(f"✗ Failed to start MCP server: {e}")
                raise typer.Exit(1) from e
        else:
            # REST API mode - create FastAPI app
            serve_app = create_multi_serve_app(
                root_dir=folder_path,
                graphs=graphs,
                metas=metas,
                verbose_print=verbose_print,
            )

            verbose_print("🚀 Starting multi-flow server...")

            protocol = "http"
            access_host = get_best_access_host(host)

            masked_key = f"{api_key[:API_KEY_MASK_LENGTH]}..." if len(api_key) > API_KEY_MASK_LENGTH else "***"

            console.print()
            console.print(
                Panel.fit(
                    f"[bold green]🎯 Folder Served Successfully![/bold green]\n\n"
                    f"[bold]Folder:[/bold] {folder_path}\n"
                    f"[bold]Flows Detected:[/bold] {len(graphs)}\n"
                    f"[bold]Server:[/bold] {protocol}://{access_host}:{port}\n"
                    f"[bold]API Key:[/bold] {masked_key}\n\n"
                    f"[dim]Discover flows:\n"
                    f"  GET {protocol}://{access_host}:{port}/flows\n"
                    f"Run a flow:\n"
                    f"  POST {protocol}://{access_host}:{port}/flows/{{flow_id}}/run[/dim]",
                    border_style="green",
                    title="🚀 Server Ready",
                )
            )
            console.print()

            try:
                uvicorn.run(
                    serve_app,
                    host=host,
                    port=port,
                    log_level=log_level.lower(),
                    access_log=verbose,
                )
            except KeyboardInterrupt:
                verbose_print("\n👋 Server stopped")
                raise typer.Exit(0) from None
            except Exception as e:
                verbose_print(f"✗ Failed to start server: {e}")
                raise typer.Exit(1) from e

        return  # successfully finished

    # ------------------------------------------------------------------
    # Original single-file / URL behaviour
    # ------------------------------------------------------------------

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
    verbose_print("Preparing graph for serving...")
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

    # Create single-flow metadata
    flow_id = flow_id_from_path(resolved_path, resolved_path.parent)
    graph.flow_id = flow_id  # annotate graph for reference

    title = resolved_path.stem
    metas = {
        flow_id: FlowMeta(
            id=flow_id,
            relative_path=str(resolved_path.name),
            title=title,
            description=None,
        )
    }
    graphs = {flow_id: graph}

    verbose_print(f"✓ Prepared single flow '{title}' (id={flow_id})")

    # Start server in appropriate mode
    if mcp:
        # For MCP mode, we start the regular FastAPI server which includes MCP endpoints
        verbose_print(f"🔧 Starting Langflow with MCP server enabled...")
        
        if mcp_transport != "sse":
            verbose_print(f"Note: Currently only SSE transport is supported for MCP. Using SSE transport.")
            mcp_transport = "sse"
        
        # Create the FastAPI app which includes MCP functionality
        serve_app = create_multi_serve_app(
            root_dir=resolved_path.parent,
            graphs=graphs,
            metas=metas,
            verbose_print=verbose_print,
        )
        
        protocol = "http"
        access_host = get_best_access_host(host)
        
        console.print()
        console.print(
            Panel.fit(
                f"[bold green]🎯 MCP Server Started![/bold green]\n\n"
                f"[bold]Mode:[/bold] MCP (SSE)\n"
                f"[bold]File:[/bold] {resolved_path}\n"
                f"[bold]Flow:[/bold] {title}\n"
                f"[bold]Server:[/bold] {protocol}://{access_host}:{port}\n\n"
                f"[dim]MCP SSE endpoint:[/dim]\n"
                f"[blue]{protocol}://{access_host}:{port}/api/v1/mcp/sse[/blue]\n\n"
                f"[dim]MCP Tools: Flow '{title}' available as executable tool\n"
                f"MCP Resources: Flow files accessible via resources\n"
                f"Note: Flow is automatically available as an MCP tool[/dim]",
                border_style="blue",
                title="🔧 MCP Server Ready",
            )
        )
        console.print()
        
        try:
            uvicorn.run(
                serve_app,
                host=host,
                port=port,
                log_level=log_level.lower(),
                access_log=verbose,
            )
        except KeyboardInterrupt:
            verbose_print("\n👋 MCP server stopped")
            raise typer.Exit(0) from None
        except Exception as e:
            verbose_print(f"✗ Failed to start MCP server: {e}")
            raise typer.Exit(1) from e
    else:
        # REST API mode
        # Create FastAPI app using multi-serve (handles single flow too)
        serve_app = create_multi_serve_app(
            root_dir=resolved_path.parent,
            graphs=graphs,
            metas=metas,
            verbose_print=verbose_print,
        )

        verbose_print("🚀 Starting single-flow server...")

        protocol = "http"
        access_host = get_best_access_host(host)

        masked_key = f"{api_key[:API_KEY_MASK_LENGTH]}..." if len(api_key) > API_KEY_MASK_LENGTH else "***"

        console.print()
        console.print(
            Panel.fit(
                f"[bold green]🎯 Single Flow Served Successfully![/bold green]\n\n"
                f"[bold]File:[/bold] {resolved_path}\n"
                f"[bold]Server:[/bold] {protocol}://{access_host}:{port}\n"
                f"[bold]API Key:[/bold] {masked_key}\n\n"
                f"[dim]Send POST requests to:[/dim]\n"
                f"[blue]{protocol}://{access_host}:{port}/flows/{flow_id}/run[/blue]\n\n"
                f"[dim]With headers:[/dim]\n"
                f"[blue]x-api-key: {masked_key}[/blue]\n\n"
                f"[dim]Or query parameter:[/dim]\n"
                f"[blue]?x-api-key={masked_key}[/blue]\n\n"
                f"[dim]Request body:[/dim]\n"
                f"[blue]{{'input_value': 'Your input message'}}[/blue]",
                title="[bold blue]Langflow Server[/bold blue]",
                border_style="blue",
            )
        )
        console.print()

        # Start the server
        try:
            uvicorn.run(
                serve_app,
                host=host,
                port=port,
                log_level=log_level,
            )
        except KeyboardInterrupt:
            verbose_print("\n👋 Server stopped")
            raise typer.Exit(0) from None
        except Exception as e:
            verbose_print(f"✗ Failed to start server: {e}")
            raise typer.Exit(1) from e
