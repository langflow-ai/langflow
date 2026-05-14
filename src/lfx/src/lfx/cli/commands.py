"""CLI commands for LFX."""

from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
from functools import partial
from pathlib import Path

import typer
import uvicorn
from asyncer import syncify
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from lfx.cli.common import (
    create_verbose_printer,
    flow_id_from_path,
    get_api_key,
    get_best_access_host,
    get_free_port,
    is_port_in_use,
    load_graph_from_path,
)
from lfx.cli.serve_app import FlowMeta, FlowRegistry, create_multi_serve_app

# Initialize console
console = Console()

# Constants
API_KEY_MASK_LENGTH = 8


@partial(syncify, raise_sync_error=False)
async def serve_command(
    script_paths: list[str] | None = typer.Argument(
        default=None,
        help=(
            "Path(s) to JSON flow file(s) (.json) or a directory containing .json files. "
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
    flow_json: str | None = typer.Option(
        None,
        "--flow-json",
        help="Inline JSON flow content as a string (alternative to script_paths)",
    ),
    *,
    stdin: bool = typer.Option(
        False,  # noqa: FBT003
        "--stdin",
        help="Read JSON flow content from stdin (alternative to script_paths)",
    ),
    check_variables: bool = typer.Option(
        True,  # noqa: FBT003
        "--check-variables/--no-check-variables",
        help="Check global variables for environment compatibility",
    ),
) -> None:
    """Serve LFX flows as a web API.

    Supports single files, inline JSON, stdin, multiple explicit files,
    and a directory of JSON flows.
    """
    from lfx.log.logger import configure

    configure(log_level=log_level)
    verbose_print = create_verbose_printer(verbose=verbose)

    # Validate exactly one input source
    has_paths = bool(script_paths)
    input_sources = [has_paths, flow_json is not None, stdin]
    if sum(input_sources) != 1:
        if sum(input_sources) == 0:
            typer.echo("Error: Must provide either path(s)/directory, --flow-json, or --stdin", err=True)
        else:
            typer.echo("Error: Cannot combine path(s), --flow-json, and --stdin. Choose exactly one.", err=True)
        raise typer.Exit(1)

    if env_file:
        if not env_file.exists():
            typer.echo(f"Error: Environment file '{env_file}' does not exist.", err=True)
            raise typer.Exit(1)
        verbose_print(f"Loading environment variables from: {env_file}")
        load_dotenv(env_file)

    try:
        api_key = get_api_key()
        verbose_print("✓ LANGFLOW_API_KEY is configured")
    except ValueError as e:
        typer.echo(f"✗ {e}", err=True)
        typer.echo("Set the LANGFLOW_API_KEY environment variable before serving.", err=True)
        raise typer.Exit(1) from e

    valid_log_levels = {"debug", "info", "warning", "error", "critical"}
    if log_level.lower() not in valid_log_levels:
        typer.echo(
            f"Error: Invalid log level '{log_level}'. Must be one of: {', '.join(sorted(valid_log_levels))}",
            err=True,
        )
        raise typer.Exit(1)

    os.environ["LANGFLOW_PRETTY_LOGS"] = "false"
    configure(log_level=log_level)

    temp_file_to_cleanup: str | None = None

    try:
        # ----------------------------------------------------------------
        # Build FlowRegistry from the input source
        # ----------------------------------------------------------------
        registry: FlowRegistry

        if flow_json is not None:
            try:
                json_data = json.loads(flow_json)
            except json.JSONDecodeError as e:
                typer.echo(f"Error: Invalid JSON content: {e}", err=True)
                raise typer.Exit(1) from e
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
                json.dump(json_data, tmp, indent=2)
                temp_file_to_cleanup = tmp.name
            paths = [Path(temp_file_to_cleanup)]
            source_display = "inline JSON"

        elif stdin:
            stdin_content = sys.stdin.read().strip()
            if not stdin_content:
                typer.echo("Error: No content received from stdin", err=True)
                raise typer.Exit(1)
            try:
                json_data = json.loads(stdin_content)
            except json.JSONDecodeError as e:
                typer.echo(f"Error: Invalid JSON content from stdin: {e}", err=True)
                raise typer.Exit(1) from e
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
                json.dump(json_data, tmp, indent=2)
                temp_file_to_cleanup = tmp.name
            paths = [Path(temp_file_to_cleanup)]
            source_display = "stdin"

        else:
            resolved = [Path(p).resolve() for p in script_paths]  # type: ignore[union-attr]

            missing = [p for p in resolved if not p.exists()]
            if missing:
                for m in missing:
                    typer.echo(f"Error: Path '{m}' does not exist.", err=True)
                raise typer.Exit(1)

            if len(resolved) == 1 and resolved[0].is_dir():
                dir_path = resolved[0]
                source_display = str(dir_path)
                try:
                    registry = await build_registry_from_directory(
                        dir_path, verbose_print, check_variables=check_variables
                    )
                except ValueError as e:
                    typer.echo(f"Error: {e}", err=True)
                    raise typer.Exit(1) from e
                verbose_print(f"✓ Loaded {len(registry)} flow(s) from directory {dir_path}")
                paths = []
            else:
                non_json = [p for p in resolved if p.suffix != ".json"]
                if non_json:
                    for p in non_json:
                        typer.echo(f"Error: '{p}' is not a .json file.", err=True)
                    raise typer.Exit(1)
                paths = resolved
                source_display = ", ".join(p.name for p in paths)

        if paths:
            try:
                registry = await build_registry_from_paths(
                    paths, verbose_print, check_variables=check_variables
                )
            except ValueError as e:
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(1) from e

        # ----------------------------------------------------------------
        # Start the server
        # ----------------------------------------------------------------
        if is_port_in_use(port, host):
            port = get_free_port(port)
            verbose_print(f"Port in use; using {port} instead")

        serve_app = create_multi_serve_app(registry=registry, verbose_print=verbose_print)
        verbose_print("🚀 Starting server...")

        protocol = "http"
        access_host = get_best_access_host(host)
        masked_key = f"{api_key[:API_KEY_MASK_LENGTH]}..." if len(api_key) > API_KEY_MASK_LENGTH else "***"

        console.print()
        console.print(
            Panel.fit(
                f"[bold green]🎯 LFX Server Started![/bold green]\n\n"
                f"[bold]Source:[/bold] {source_display}\n"
                f"[bold]Flows:[/bold] {len(registry)}\n"
                f"[bold]Server:[/bold] {protocol}://{access_host}:{port}\n"
                f"[bold]API Key:[/bold] {masked_key}\n\n"
                f"[dim]List flows:[/dim]\n"
                f"[blue]{protocol}://{access_host}:{port}/flows[/blue]\n\n"
                f"[dim]Upload new flow:[/dim]\n"
                f"[blue]POST {protocol}://{access_host}:{port}/flows/upload/[/blue]\n\n"
                f"[dim]Run a flow:[/dim]\n"
                f"[blue]POST {protocol}://{access_host}:{port}/flows/{{flow_id}}/run[/blue]",
                title="[bold blue]LFX Server[/bold blue]",
                border_style="blue",
            )
        )
        console.print()

        try:
            config = uvicorn.Config(serve_app, host=host, port=port, log_level=log_level)
            server = uvicorn.Server(config)
            await server.serve()
        except KeyboardInterrupt:
            verbose_print("\n👋 Server stopped")
            raise typer.Exit(0) from None
        except Exception as e:
            verbose_print(f"✗ Failed to start server: {e}")
            raise typer.Exit(1) from e

    finally:
        if temp_file_to_cleanup:
            with contextlib.suppress(OSError):
                Path(temp_file_to_cleanup).unlink()


async def _load_graph_and_meta(
    path: Path,
    root_dir: Path,
    verbose_print,
    *,
    check_variables: bool,
) -> tuple:
    """Load and prepare one graph, returning (graph, FlowMeta)."""
    graph = await load_graph_from_path(path, path.suffix, verbose_print, verbose=False)
    graph.prepare()
    if check_variables:
        from lfx.cli.validation import validate_global_variables_for_env

        errors = validate_global_variables_for_env(graph)
        if errors:
            msg = f"Global variable validation failed for {path.name}: {'; '.join(errors)}"
            raise ValueError(msg)
    flow_id = flow_id_from_path(path, root_dir)
    graph.flow_id = flow_id
    meta = FlowMeta(
        id=flow_id,
        relative_path=str(path.relative_to(root_dir)),
        title=path.stem,
        description=None,
    )
    return graph, meta


async def build_registry_from_directory(
    dir_path: Path,
    verbose_print,
    *,
    check_variables: bool,
) -> FlowRegistry:
    """Build a FlowRegistry by scanning *dir_path* for ``*.json`` files (non-recursive)."""
    json_files = sorted(dir_path.glob("*.json"))
    if not json_files:
        msg = f"No .json files found in directory: {dir_path}"
        raise ValueError(msg)

    registry = FlowRegistry()
    errors: list[str] = []
    for path in json_files:
        try:
            graph, meta = await _load_graph_and_meta(path, dir_path, verbose_print, check_variables=check_variables)
            registry.add(graph, meta)
            verbose_print(f"✓ Loaded flow '{meta.title}' (id={meta.id})")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.name}: {exc}")

    if errors:
        msg = "Failed to load flows:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(msg)

    return registry


async def build_registry_from_paths(
    paths: list[Path],
    verbose_print,
    *,
    check_variables: bool,
) -> FlowRegistry:
    """Build a FlowRegistry from an explicit list of ``*.json`` paths."""
    registry = FlowRegistry()
    errors: list[str] = []
    for path in paths:
        try:
            graph, meta = await _load_graph_and_meta(path, path.parent, verbose_print, check_variables=check_variables)
            registry.add(graph, meta)
            verbose_print(f"✓ Loaded flow '{meta.title}' (id={meta.id})")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.name}: {exc}")

    if errors:
        msg = "Failed to load flows:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(msg)

    return registry
