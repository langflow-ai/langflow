"""CLI commands for Langflow."""

# Import moved to avoid circular import issues
from __future__ import annotations

import json
import os
import sys
import tempfile
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
    extract_script_docstring,
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
DOCSTRING_PREVIEW_LENGTH_SINGLE = 60
DOCSTRING_PREVIEW_LENGTH_FOLDER = 100

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
    script_path: str | None = typer.Argument(
        None,
        help=(
            "Path to Python script (.py), JSON flow (.json), folder with flows, "
            "GitHub repo URL, or URL to a Python script. "
            "Optional when using --flow-json or --stdin."
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
    flow_json: str | None = typer.Option(
        None,
        "--flow-json",
        help="Inline JSON flow content as a string (alternative to script_path)",
    ),
    stdin: bool = typer.Option(  # noqa: FBT001
        False,  # noqa: FBT003
        "--stdin",
        help="Read JSON flow content from stdin (alternative to script_path)",
    ),
) -> None:
    """Serve Langflow flows as a web API or MCP server.

    Supports single files, folders, GitHub repositories, inline JSON, and stdin input.

    Examples:
        # Serve from file
        langflow serve my_flow.json

        # Serve inline JSON
        langflow serve --flow-json '{"nodes": [...], "edges": [...]}'

        # Serve from stdin
        cat my_flow.json | langflow serve --stdin
        echo '{"nodes": [...]}' | langflow serve --stdin
    """
    verbose_print = create_verbose_printer(verbose=verbose)

    # Validate input sources - exactly one must be provided
    input_sources = [script_path is not None, flow_json is not None, stdin]
    if sum(input_sources) != 1:
        if sum(input_sources) == 0:
            verbose_print("Error: Must provide either script_path, --flow-json, or --stdin")
        else:
            verbose_print("Error: Cannot use script_path, --flow-json, and --stdin together. Choose exactly one.")
        raise typer.Exit(1)

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
            verbose_print(
                f"Warning: Only SSE transport is currently supported. Using 'sse' instead of '{mcp_transport}'"
            )
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
    # Disable pretty logs for serve command to avoid ANSI codes in API responses
    os.environ["LANGFLOW_PRETTY_LOGS"] = "false"
    verbose_print(f"Configuring logging with level: {log_level}")
    configure(log_level=log_level)

    # ------------------------------------------------------------------
    # Handle inline JSON content or stdin input
    # ------------------------------------------------------------------
    temp_file_to_cleanup = None

    if flow_json is not None:
        verbose_print("Processing inline JSON content...")
        try:
            # Validate JSON syntax
            json_data = json.loads(flow_json)
            verbose_print("✓ JSON content is valid")

            # Create a temporary file with the JSON content
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_file:
                json.dump(json_data, temp_file, indent=2)
                temp_file_to_cleanup = temp_file.name

            script_path = temp_file_to_cleanup
            verbose_print(f"✓ Created temporary file: {script_path}")

        except json.JSONDecodeError as e:
            verbose_print(f"Error: Invalid JSON content: {e}")
            raise typer.Exit(1) from e
        except Exception as e:
            verbose_print(f"Error processing JSON content: {e}")
            raise typer.Exit(1) from e

    elif stdin:
        verbose_print("Reading JSON content from stdin...")
        try:
            # Read all content from stdin
            stdin_content = sys.stdin.read().strip()
            if not stdin_content:
                verbose_print("Error: No content received from stdin")
                raise typer.Exit(1)

            # Validate JSON syntax
            json_data = json.loads(stdin_content)
            verbose_print("✓ JSON content from stdin is valid")

            # Create a temporary file with the JSON content
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_file:
                json.dump(json_data, temp_file, indent=2)
                temp_file_to_cleanup = temp_file.name

            script_path = temp_file_to_cleanup
            verbose_print(f"✓ Created temporary file from stdin: {script_path}")

        except json.JSONDecodeError as e:
            verbose_print(f"Error: Invalid JSON content from stdin: {e}")
            raise typer.Exit(1) from e
        except Exception as e:
            verbose_print(f"Error reading from stdin: {e}")
            raise typer.Exit(1) from e

    try:
        # ------------------------------------------------------------------
        # Single-file vs directory detection
        # ------------------------------------------------------------------

        # 1) Remote repository / ZIP URL deployment ---------------------------------
        if script_path is None:
            verbose_print("Error: script_path is None after input validation")
            raise typer.Exit(1)

        if isinstance(script_path, str) and is_url(script_path) and not script_path.lower().endswith(".py"):
            try:
                folder_path = download_and_extract_repo(script_path, verbose_print)
            except Exception as exc:
                verbose_print(f"Error downloading repository: {exc}")
                raise typer.Exit(1) from exc

            # Treat extracted folder as local directory (re-use logic below)
            script_path_obj = folder_path
        else:
            if script_path is None:
                verbose_print("Error: script_path is None after input validation")
                raise typer.Exit(1)
            script_path_obj = Path(script_path)

        if script_path_obj.exists() and script_path_obj.is_dir():
            # --------------------------------------------------------------
            # Folder deployment - expose all *.json flows under /flows/{id}
            # --------------------------------------------------------------
            folder_path = script_path_obj.resolve()

            if str(folder_path) not in sys.path:
                sys.path.insert(0, str(folder_path))

            json_files: list[Path] = [p for p in folder_path.rglob("*.json") if p.is_file()]
            py_files: list[Path] = [p for p in folder_path.rglob("*.py") if p.is_file()]

            all_files = json_files + py_files
            if not all_files:
                verbose_print("Error: No .json or .py flow files found in the provided folder.")
                raise typer.Exit(1)

            graphs: dict[str, Graph] = {}
            metas: dict[str, FlowMeta] = {}

            # Process JSON files
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
                    verbose_print(f"✓ Prepared JSON flow '{title}' (id={flow_id})")
                except Exception as exc:
                    verbose_print(f"✗ Failed loading JSON flow '{json_file}': {exc}")
                    raise typer.Exit(1) from exc

            # Process Python files
            for py_file in py_files:
                try:
                    graph = load_graph_from_path(py_file, ".py", verbose_print, verbose=verbose)
                    flow_id = flow_id_from_path(py_file, folder_path)
                    graph.flow_id = flow_id  # annotate graph for reference
                    graph.prepare()

                    title = py_file.stem

                    # Extract docstring for description
                    description = extract_script_docstring(py_file)
                    if description:
                        preview = description[:DOCSTRING_PREVIEW_LENGTH_SINGLE]
                        if len(description) > DOCSTRING_PREVIEW_LENGTH_SINGLE:
                            preview += "..."
                        verbose_print(f"✓ Found docstring for '{title}': {preview}")

                    metas[flow_id] = FlowMeta(
                        id=flow_id,
                        relative_path=str(py_file.relative_to(folder_path)),
                        title=title,
                        description=description,
                    )
                    graphs[flow_id] = graph
                    verbose_print(f"✓ Prepared Python flow '{title}' (id={flow_id})")
                except Exception as exc:
                    verbose_print(f"✗ Failed loading Python flow '{py_file}': {exc}")
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
                verbose_print("🔧 Starting Langflow with MCP server enabled...")

                if mcp_transport != "sse":
                    verbose_print("Note: Currently only SSE transport is supported for MCP. Using SSE transport.")
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
        if script_path is None:
            verbose_print("Error: script_path is None after input validation")
            raise typer.Exit(1)
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

        # Extract docstring for Python files
        description = None
        if file_extension == ".py":
            description = extract_script_docstring(resolved_path)
            if description:
                preview = description[:DOCSTRING_PREVIEW_LENGTH_FOLDER]
                if len(description) > DOCSTRING_PREVIEW_LENGTH_FOLDER:
                    preview += "..."
                verbose_print(f"✓ Found docstring for description: {preview}")
            else:
                verbose_print("No module docstring found")

        metas = {
            flow_id: FlowMeta(
                id=flow_id,
                relative_path=str(resolved_path.name),
                title=title,
                description=description,
            )
        }
        graphs = {flow_id: graph}

        source_display = "inline JSON" if flow_json else "stdin" if stdin else str(resolved_path)
        verbose_print(f"✓ Prepared single flow '{title}' from {source_display} (id={flow_id})")

        # Start server in appropriate mode
        if mcp:
            # For MCP mode, we start the regular FastAPI server which includes MCP endpoints
            verbose_print("🔧 Starting Langflow with MCP server enabled...")

            if mcp_transport != "sse":
                verbose_print("Note: Currently only SSE transport is supported for MCP. Using SSE transport.")
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
                    f"[bold]Source:[/bold] {source_display}\n"
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
                    f"[bold]Source:[/bold] {source_display}\n"
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

    finally:
        # Clean up temporary file if created
        if temp_file_to_cleanup:
            try:
                Path(temp_file_to_cleanup).unlink()
                verbose_print(f"✓ Cleaned up temporary file: {temp_file_to_cleanup}")
            except OSError as e:
                verbose_print(f"Warning: Failed to clean up temporary file {temp_file_to_cleanup}: {e}")
