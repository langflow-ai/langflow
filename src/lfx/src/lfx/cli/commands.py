"""CLI commands for LFX."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import typer
import uvicorn
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
)
from lfx.cli.script_loader import find_graph_variable, load_graph_from_script
from lfx.cli.serve_app import FlowAlreadyRegisteredError, FlowMeta, FlowRegistry, create_multi_serve_app
from lfx.load import load_flow_from_json
from lfx.utils.flow_envelope import merge_flow_envelope, split_flow_envelope

if TYPE_CHECKING:
    from collections.abc import Callable

    from lfx.cli.flow_store import FlowStore

# Initialize console
console = Console()

# Constants
API_KEY_MASK_LENGTH = 8


def _gate_flow_for_serve(
    payload: dict,
    upgrade_flow: str,
    *,
    verbose: bool,
) -> dict:
    """Run the shared ``--upgrade-flow`` gate on a parsed flow payload.

    Splits any outer ``{"data": ...}`` envelope, runs ``apply_upgrade_gate`` on the inner
    graph (the same gate ``lfx run`` uses), then re-attaches the envelope so the result is
    loader-ready — ``aload_flow_from_json`` requires the ``{"data": ...}`` wrapper.

    Raises:
        typer.Exit: if the payload is not a JSON object, or the gate aborts (incompatible in
            ``check`` mode, or blocked/breaking in ``safe`` mode).
    """
    from lfx.upgrade.cli_gate import UpgradeFlowError, apply_upgrade_gate

    try:
        outer_envelope, inner = split_flow_envelope(payload)
    except TypeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e
    try:
        inner, applied = apply_upgrade_gate(inner, mode=upgrade_flow)
    except UpgradeFlowError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e
    if applied and verbose:
        typer.echo(f"Applied {applied} safe component upgrade(s).")
    return merge_flow_envelope(outer_envelope, inner, wrap_bare=True)


async def _build_serve_registry(
    *,
    script_paths: list[str] | None,
    flow_json: str | None,
    stdin: bool,
    check_variables: bool,
    no_env_fallback: bool,
    flow_store: FlowStore,
    verbose_print: Callable[[str], None],
    upgrade_flow: str | None = None,
    verbose: bool = False,
) -> tuple[FlowRegistry, str | None]:
    """Build the FlowRegistry from startup inputs.

    Returns (registry, temp_file_path_or_None). Caller must unlink the temp
    file if not None.

    When ``upgrade_flow`` is set, the flow is run through the shared ``--upgrade-flow`` gate
    before the registry is built. This is supported for inline JSON, stdin, and a single
    ``.json`` file path; directories, multiple paths, and ``.py`` scripts are rejected.
    """
    temp_file_to_cleanup: str | None = None

    if flow_json is not None or stdin:
        if flow_json is not None:
            try:
                json_data = json.loads(flow_json)
            except json.JSONDecodeError as e:
                typer.echo(f"Error: Invalid JSON content: {e}", err=True)
                raise typer.Exit(1) from e
        else:
            stdin_content = sys.stdin.read().strip()
            if not stdin_content:
                typer.echo("Error: No content received from stdin", err=True)
                raise typer.Exit(1)
            try:
                json_data = json.loads(stdin_content)
            except json.JSONDecodeError as e:
                typer.echo(f"Error: Invalid JSON content from stdin: {e}", err=True)
                raise typer.Exit(1) from e
        if upgrade_flow:
            json_data = _gate_flow_for_serve(json_data, upgrade_flow, verbose=verbose)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(json_data, tmp, indent=2)
            temp_file_to_cleanup = tmp.name
        try:
            registry = await build_registry_from_paths(
                [Path(temp_file_to_cleanup)],
                verbose_print,
                check_variables=check_variables,
                no_env_fallback=no_env_fallback,
                store=flow_store,
            )
        except ValueError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1) from e

    elif script_paths:
        resolved = [Path(p).resolve() for p in script_paths]
        missing = [p for p in resolved if not p.exists()]
        if missing:
            for m in missing:
                typer.echo(f"Error: Path '{m}' does not exist.", err=True)
            raise typer.Exit(1)

        if upgrade_flow:
            # --upgrade-flow with a path supports exactly one .json flow file: directories,
            # multiple files, and .py scripts can't be safely upgraded in place here.
            if len(resolved) != 1 or resolved[0].is_dir() or resolved[0].suffix.lower() != ".json":
                typer.echo(
                    "Error: --upgrade-flow with a path supports exactly one .json flow file "
                    "(not directories, multiple files, or .py scripts).",
                    err=True,
                )
                raise typer.Exit(1)
            try:
                payload = json.loads(resolved[0].read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                typer.echo(f"Error: --upgrade-flow: could not read flow file '{resolved[0]}': {e}", err=True)
                raise typer.Exit(1) from e
            gated = _gate_flow_for_serve(payload, upgrade_flow, verbose=verbose)
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
                json.dump(gated, tmp, indent=2)
                temp_file_to_cleanup = tmp.name
            try:
                registry = await build_registry_from_paths(
                    [Path(temp_file_to_cleanup)],
                    verbose_print,
                    check_variables=check_variables,
                    no_env_fallback=no_env_fallback,
                    store=flow_store,
                )
            except ValueError as e:
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(1) from e

        elif len(resolved) == 1 and resolved[0].is_dir():
            dir_path = resolved[0]
            try:
                registry = await build_registry_from_directory(
                    dir_path,
                    verbose_print,
                    check_variables=check_variables,
                    no_env_fallback=no_env_fallback,
                    store=flow_store,
                )
            except ValueError as e:
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(1) from e
            verbose_print(f"Loaded {len(registry)} flow(s) from directory {dir_path}")
        else:
            non_supported = [p for p in resolved if p.suffix not in {".json", ".py"}]
            if non_supported:
                for p in non_supported:
                    typer.echo(f"Error: '{p}' must be a .json or .py file.", err=True)
                raise typer.Exit(1)
            try:
                registry = await build_registry_from_paths(
                    resolved,
                    verbose_print,
                    check_variables=check_variables,
                    no_env_fallback=no_env_fallback,
                    store=flow_store,
                )
            except ValueError as e:
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(1) from e

    else:
        if upgrade_flow:
            typer.echo(
                "Error: --upgrade-flow requires a JSON flow source (--flow-json, --stdin, or a .json file path).",
                err=True,
            )
            raise typer.Exit(1)
        registry = FlowRegistry(no_env_fallback=no_env_fallback, store=flow_store)
        verbose_print("Starting with empty registry — flows can be uploaded at runtime")

    return registry, temp_file_to_cleanup


def serve_command(
    script_paths: list[str] | None = typer.Argument(
        default=None,
        help=(
            "Path(s) to JSON flow file(s) (.json), Python script(s) (.py), or a directory "
            "containing .json files (top-level only, non-recursive). "
            "Optional when using --flow-json or --stdin."
        ),
    ),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind the server to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind the server to"),
    workers: int = typer.Option(
        1,
        "--workers",
        "-w",
        help="Number of uvicorn worker processes. Use with --flow-dir for multi-worker flow sharing.",
    ),
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
    flow_dir: Path | None = typer.Option(
        None,
        "--flow-dir",
        help=(
            "Directory for filesystem-backed flow storage. "
            "All uvicorn workers sharing this path will serve the same flows. "
            "Use /tmp/lfx-flows for single-pod sharing or a PVC mount for cross-pod. "
            "Defaults to in-memory only when omitted."
        ),
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
    no_env_fallback: bool = typer.Option(
        False,  # noqa: FBT003
        "--no-env-fallback/--env-fallback",
        help=(
            "Disable os.environ fallback for credential variables. "
            "Variables not supplied via global_vars on each request resolve to None "
            "instead of reading from the process environment."
        ),
    ),
    upgrade_flow: str | None = None,
) -> None:
    """Serve LFX flows as a web API.

    Supports single files, inline JSON, stdin, multiple explicit files,
    and a directory of JSON flows.
    """
    from lfx.log.logger import configure

    configure(log_level=log_level)
    verbose_print = create_verbose_printer(verbose=verbose)

    # Validate at most one input source
    has_paths = bool(script_paths)
    input_sources = [has_paths, flow_json is not None, stdin]
    if sum(input_sources) > 1:
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
        verbose_print("LANGFLOW_API_KEY is configured")
    except ValueError as e:
        typer.echo(str(e), err=True)
        typer.echo("Set the LANGFLOW_API_KEY environment variable before serving.", err=True)
        raise typer.Exit(1) from e

    valid_log_levels = {"debug", "info", "warning", "error", "critical"}
    if log_level.lower() not in valid_log_levels:
        typer.echo(
            f"Error: Invalid log level '{log_level}'. Must be one of: {', '.join(sorted(valid_log_levels))}",
            err=True,
        )
        raise typer.Exit(1)

    if workers < 1:
        typer.echo("Error: --workers must be at least 1.", err=True)
        raise typer.Exit(1)

    os.environ["LANGFLOW_PRETTY_LOGS"] = "false"
    configure(log_level=log_level)

    from lfx.cli.flow_store import FilesystemFlowStore, NullFlowStore

    flow_store = FilesystemFlowStore(flow_dir) if flow_dir else NullFlowStore()

    if workers > 1 and flow_dir is None:
        typer.echo(
            "Warning: --workers > 1 without --flow-dir means each worker has an isolated "
            "in-memory registry. Flows uploaded to one worker will not be visible to others. "
            "Pass --flow-dir to enable shared flow storage across workers.",
            err=True,
        )

    if workers > 1 and flow_dir is not None and script_paths:
        # With --flow-dir, workers skip LFX_SERVE_STARTUP_PATHS and rely on warm_from_store().
        # .py files produce no raw_json so they can't be written to the store — workers would
        # silently start without those flows.  Without --flow-dir workers re-execute the .py
        # file directly from LFX_SERVE_STARTUP_PATHS, which works fine.
        py_paths = [p for p in script_paths if Path(p).suffix == ".py"]
        if py_paths:
            for p in py_paths:
                typer.echo(
                    f"Error: '{Path(p).name}' (.py) cannot be used with --workers > 1 and --flow-dir. "
                    "Python graphs cannot be serialized to the store, so workers would start without "
                    "those flows. Use a .json export, omit --flow-dir, or use --workers 1.",
                    err=True,
                )
            raise typer.Exit(1)

    # Determine display name for startup panel
    if flow_json is not None:
        source_display = "inline JSON"
    elif stdin:
        source_display = "stdin"
    elif script_paths:
        resolved_display = [Path(p).resolve() for p in script_paths]
        if len(resolved_display) == 1 and resolved_display[0].is_dir():
            source_display = str(resolved_display[0])
        else:
            source_display = ", ".join(Path(p).name for p in script_paths)
    else:
        source_display = "none (upload flows via POST /flows/upload/)"

    temp_file_to_cleanup: str | None = None
    try:
        registry, temp_file_to_cleanup = asyncio.run(
            _build_serve_registry(
                script_paths=script_paths,
                flow_json=flow_json,
                stdin=stdin,
                check_variables=check_variables,
                no_env_fallback=no_env_fallback,
                flow_store=flow_store,
                verbose_print=verbose_print,
                upgrade_flow=upgrade_flow,
                verbose=verbose,
            )
        )

        if flow_dir:
            if workers == 1:
                # Single-worker: warm now so the startup panel shows the real count and the
                # first request to any pre-existing flow doesn't pay a cold-load penalty.
                # Multi-worker: each worker warms inside create_serve_app(); the parent can't
                # safely warm and pass graphs across processes, so we skip it here.
                registry.warm_from_store()
            verbose_print(f"Flow store at {flow_dir} ({len(registry)} flows available)")

        if is_port_in_use(port, host):
            port = get_free_port(port)
            verbose_print(f"Port in use; using {port} instead")

        verbose_print("Starting server...")

        protocol = "http"
        access_host = get_best_access_host(host)
        masked_key = f"{api_key[:API_KEY_MASK_LENGTH]}..." if len(api_key) > API_KEY_MASK_LENGTH else "***"
        server_line = f"{protocol}://{access_host}:{port}"
        if access_host != host:
            server_line += f"  [dim](bound to {host}:{port})[/dim]"

        console.print()
        console.print(
            Panel.fit(
                f"[bold green]LFX Server Ready[/bold green]\n\n"
                f"[bold]Source:[/bold] {source_display}\n"
                f"[bold]Flows:[/bold] {len(registry)}\n"
                f"[bold]Workers:[/bold] {workers}\n"
                f"[bold]Server:[/bold] {server_line}\n"
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
            if workers > 1:
                # uvicorn requires an import string (not an app object) for multi-worker mode.
                # Set env vars so each worker's create_serve_app() factory can reconstruct config.
                # The parent's in-memory app is never passed to workers — each worker calls
                # create_serve_app() fresh, so we skip building the app here.
                from lfx.cli.serve_app import (
                    _SERVE_FLOW_DIR_ENV,
                    _SERVE_NO_ENV_FALLBACK_ENV,
                    _SERVE_STARTUP_PATHS_ENV,
                )

                os.environ[_SERVE_FLOW_DIR_ENV] = str(flow_dir) if flow_dir else ""
                os.environ[_SERVE_NO_ENV_FALLBACK_ENV] = "1" if no_env_fallback else "0"

                # When flow_dir is set, startup flows are already in the store (written by
                # _build_serve_registry above) so workers load them via warm_from_store().
                # When flow_dir is NOT set, workers must re-read the original files.
                startup_paths_for_workers: list[str] = []
                if not flow_dir:
                    if script_paths:
                        startup_paths_for_workers = [str(Path(p).resolve()) for p in script_paths]
                    elif temp_file_to_cleanup:
                        startup_paths_for_workers = [temp_file_to_cleanup]
                os.environ[_SERVE_STARTUP_PATHS_ENV] = json.dumps(startup_paths_for_workers)
                try:
                    uvicorn.run(
                        "lfx.cli.serve_app:create_serve_app",
                        host=host,
                        port=port,
                        workers=workers,
                        log_level=log_level,
                        factory=True,
                    )
                finally:
                    # Only remove the keys we set above — a prefix sweep would also delete
                    # any LFX_SERVE_* var the operator intentionally exported before launch.
                    for k in (_SERVE_FLOW_DIR_ENV, _SERVE_NO_ENV_FALLBACK_ENV, _SERVE_STARTUP_PATHS_ENV):
                        os.environ.pop(k, None)
            else:
                serve_app = create_multi_serve_app(registry=registry)
                uvicorn.run(serve_app, host=host, port=port, workers=1, log_level=log_level)
        except KeyboardInterrupt:
            verbose_print("\nServer stopped")
            raise typer.Exit(0) from None
        except Exception as e:
            verbose_print(f"Failed to start server: {e}")
            raise typer.Exit(1) from e

    finally:
        if temp_file_to_cleanup:
            with contextlib.suppress(OSError):
                Path(temp_file_to_cleanup).unlink()


async def _load_graph_and_meta(
    path: Path,
    root_dir: Path,
    *,
    check_variables: bool,
) -> tuple:
    """Load and prepare one graph, returning (graph, FlowMeta, raw_json | None).

    raw_json is the parsed flow dict for .json files; None for .py files
    (which cannot be round-tripped to JSON for store persistence).
    """
    raw_json: dict | None = None
    try:
        if path.suffix == ".py":
            find_graph_variable(path)  # validates a 'graph' variable exists
            graph = await load_graph_from_script(path)
        else:
            raw_json = json.loads(path.read_text(encoding="utf-8"))
            graph = load_flow_from_json(raw_json)
    except Exception as exc:
        msg = f"Failed to load {path.name}: {exc}"
        raise ValueError(msg) from exc
    graph.prepare()
    if check_variables:
        from lfx.cli.validation import validate_global_variables_for_env

        errors = validate_global_variables_for_env(graph)
        if errors:
            msg = f"Global variable validation failed for {path.name}: {'; '.join(errors)}"
            raise ValueError(msg)
    path_flow_id = flow_id_from_path(path, root_dir)
    # Prefer the JSON's own id so the startup ID matches what workers reconstruct
    # from the store (which also prefers raw_json["id"]).  Fall back to the
    # path-derived UUID when the JSON has no id (e.g. hand-written flows).
    flow_id = (raw_json.get("id") if raw_json else None) or path_flow_id
    graph.flow_id = flow_id
    meta = FlowMeta(
        id=flow_id,
        relative_path=str(path.relative_to(root_dir)),
        title=(raw_json.get("name") or path.stem) if raw_json else path.stem,
        description=(raw_json.get("description")) if raw_json else None,
    )
    return graph, meta, raw_json


async def _populate_registry(
    paths: list[Path],
    root_dir: Path,
    registry: FlowRegistry,
    verbose_print: Callable[[str], None],
    *,
    check_variables: bool,
) -> None:
    """Load each path into *registry*, collecting errors and raising at the end."""
    errors: list[str] = []
    for path in paths:
        try:
            graph, meta, raw_json = await _load_graph_and_meta(path, root_dir, check_variables=check_variables)
            registry.add(graph, meta, raw_json=raw_json)
            verbose_print(f"Loaded flow '{meta.title}' (id={meta.id})")
        except FlowAlreadyRegisteredError:
            verbose_print(f"Skipping duplicate flow id={meta.id} from {path.name}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.name}: {exc}")
    if errors:
        msg = "Failed to load flows:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(msg)


async def build_registry_from_directory(
    dir_path: Path,
    verbose_print: Callable[[str], None],
    *,
    check_variables: bool,
    no_env_fallback: bool = False,
    store: FlowStore | None = None,
) -> FlowRegistry:
    """Build a FlowRegistry by scanning *dir_path* for ``*.json`` files (non-recursive).

    Callers that want pre-existing store flows (e.g. from a prior run) to be
    reachable are responsible for calling ``registry.warm_from_store()`` after
    this returns.  ``serve_command`` does this in the right place; calling it
    here too would cause double-loading when ``store`` backs the same directory.
    """
    from lfx.cli.flow_store import NullFlowStore

    json_files = sorted(dir_path.glob("*.json"))
    if not json_files:
        msg = f"No .json files found in directory: {dir_path}"
        raise ValueError(msg)

    registry = FlowRegistry(no_env_fallback=no_env_fallback, store=store or NullFlowStore())
    await _populate_registry(json_files, dir_path, registry, verbose_print, check_variables=check_variables)
    return registry


async def build_registry_from_paths(
    paths: list[Path],
    verbose_print: Callable[[str], None],
    *,
    check_variables: bool,
    no_env_fallback: bool = False,
    store: FlowStore | None = None,
) -> FlowRegistry:
    """Build a FlowRegistry from an explicit list of ``.json`` or ``.py`` paths.

    Callers that want pre-existing store flows to be reachable are responsible
    for calling ``registry.warm_from_store()`` after this returns.
    ``serve_command`` does this in the right place.
    """
    from lfx.cli.flow_store import NullFlowStore

    # Use a shared root so same-named files in different directories get distinct IDs.
    common_root = (
        Path(os.path.commonpath([str(p) for p in paths])) if len(paths) > 1 else paths[0].parent if paths else Path()
    )
    registry = FlowRegistry(no_env_fallback=no_env_fallback, store=store or NullFlowStore())
    await _populate_registry(paths, common_root, registry, verbose_print, check_variables=check_variables)
    return registry
