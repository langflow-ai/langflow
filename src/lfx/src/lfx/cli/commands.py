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

from lfx.cli import _serve_help
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
    from lfx.cli.serve_identity import IdentityConfig

# Initialize console
console = Console()

# Constants
API_KEY_MASK_LENGTH = 8

# Default gunicorn worker recycling (multi-worker, Unix). When --max-requests is unset we
# still recycle every ~this-many requests so long-lived workers shed accumulated memory /
# per-worker caches; jitter (10%) staggers workers so they don't all recycle on the same
# request count. Explicit --max-requests 0 disables recycling; explicit N overrides this.
DEFAULT_MAX_REQUESTS = 1000
# Default gunicorn worker timeout (seconds) for multi-worker serving. gunicorn's own
# default is 30s, which would kill long LLM flows. None (omitted --timeout) maps to this.
DEFAULT_TIMEOUT = 120


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
        help=_serve_help.FLOW_DIR,
    ),
    max_requests: int | None = typer.Option(
        None,
        "--max-requests",
        help=_serve_help.MAX_REQUESTS,
    ),
    timeout: int | None = typer.Option(
        None,
        "--timeout",
        help=_serve_help.TIMEOUT,
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
        help=_serve_help.NO_ENV_FALLBACK,
    ),
    reset_environ: bool = typer.Option(
        False,  # noqa: FBT003
        "--reset-environ/--no-reset-environ",
        help=_serve_help.RESET_ENVIRON,
    ),
    sync_workers: bool = typer.Option(
        False,  # noqa: FBT003
        "--use-sync-workers/--use-async-workers",
        help=_serve_help.SYNC_WORKERS,
    ),
    # Plain defaults (not typer.Option): the CLI options live on serve_command_wrapper,
    # which passes these through. Plain defaults keep clean values even if a direct
    # caller omits them — a typer.Option default would leak an OptionInfo object
    # (e.g. mode would arrive as <typer.models.OptionInfo>, not "off").
    identity_mode: str = "off",
    identity_jwt_issuer: str | None = None,
    identity_jwt_audience: str | None = None,
    identity_jwt_jwks_url: str | None = None,
    identity_claim: str = "sub",
    identity_jwt_header: str = "Authorization",
    identity_header: str = "X-Consumer-Username",
    identity_jwt_allow_insecure_http: bool = False,
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

    # When serve_command is invoked directly (not via the typer CLI), an omitted option arrives
    # as a typer OptionInfo sentinel rather than its real default. Normalize up front so the
    # gunicorn math, the single-worker warning, and the worker env see clean values — an
    # un-normalized OptionInfo is truthy, which would silently flip the bool flags on.
    if not isinstance(max_requests, int):
        max_requests = None
    if not isinstance(timeout, int):
        timeout = None
    if not isinstance(reset_environ, bool):
        reset_environ = False
    if not isinstance(sync_workers, bool):
        sync_workers = False

    from lfx.cli.serve_identity import IdentityConfig, IdentityConfigError

    try:
        identity_config = IdentityConfig(
            mode=identity_mode,  # type: ignore[arg-type]
            jwt_issuer=identity_jwt_issuer,
            jwt_audience=identity_jwt_audience,
            jwt_jwks_url=identity_jwt_jwks_url,
            claim=identity_claim,
            jwt_header=identity_jwt_header,
            trusted_header=identity_header,
            allow_insecure_http=identity_jwt_allow_insecure_http,
        )
    except IdentityConfigError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e

    os.environ["LANGFLOW_PRETTY_LOGS"] = "false"
    configure(log_level=log_level)

    from lfx.cli.flow_store import FilesystemFlowStore, NullFlowStore

    flow_store = FilesystemFlowStore(flow_dir) if flow_dir else NullFlowStore()

    if workers > 1 and flow_dir is None:
        typer.echo(
            "Warning: --workers > 1 without --flow-dir means each worker has an isolated "
            "in-memory registry. Flows uploaded to one worker will not be visible to others "
            "(and with --max-requests recycling, uploaded flows do not survive worker recycling "
            "at all). Pass --flow-dir to enable shared flow storage across workers.",
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
                _launch_workers(
                    host=host,
                    port=port,
                    workers=workers,
                    log_level=log_level,
                    flow_dir=flow_dir,
                    no_env_fallback=no_env_fallback,
                    script_paths=script_paths,
                    temp_file_to_cleanup=temp_file_to_cleanup,
                    verbose_print=verbose_print,
                    max_requests=max_requests,
                    reset_environ=reset_environ,
                    sync_workers=sync_workers,
                    timeout=timeout,
                    identity_config=identity_config,
                )
            else:
                from lfx.cli.serve_app import _SERVE_RESET_ENVIRON_ENV

                # These flags only affect multi-worker serving; with one worker they are
                # silently inert, so warn loudly rather than appear to honor them.
                if max_requests is not None or sync_workers or timeout is not None:
                    typer.echo(
                        "Warning: --max-requests/--use-sync-workers/--timeout apply only to multi-worker "
                        "serving (--workers > 1) and are ignored with a single worker.",
                        err=True,
                    )

                # Single worker also serves many requests warm, so honor --reset-environ
                # here (read per request by guarded_execute). --use-sync-workers is a
                # multi-worker routing concern and has no effect with one worker.
                os.environ[_SERVE_RESET_ENVIRON_ENV] = "1" if reset_environ else "0"
                try:
                    serve_app = create_multi_serve_app(registry=registry, identity_config=identity_config)
                    uvicorn.run(serve_app, host=host, port=port, workers=1, log_level=log_level)
                finally:
                    # Symmetry with _launch_workers: don't leave our key in the parent env.
                    os.environ.pop(_SERVE_RESET_ENVIRON_ENV, None)
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


@contextlib.contextmanager
def _exported_env(env: dict[str, str]):
    """Export ``env`` into ``os.environ`` for the body, then restore the prior state.

    Keys we added are removed; keys we overwrote are restored to their original value (not a
    prefix sweep), so a ``LFX_SERVE_*`` var the operator exported before launch survives with
    its own value rather than being deleted.
    """
    sentinel = object()
    previous = {key: os.environ.get(key, sentinel) for key in env}
    for key, value in env.items():
        os.environ[key] = value
    try:
        yield
    finally:
        for key, prev in previous.items():
            if prev is sentinel:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev


def _launch_workers(
    *,
    host: str,
    port: int,
    workers: int,
    log_level: str,
    flow_dir: Path | None,
    no_env_fallback: bool,
    script_paths: list[str] | None,
    temp_file_to_cleanup: str | None,
    verbose_print: Callable[[str], None],
    max_requests: int | None,
    reset_environ: bool = False,
    sync_workers: bool = False,
    timeout: int | None = None,
    identity_config: IdentityConfig | None = None,
) -> None:
    """Launch ``workers`` worker processes for ``lfx serve --workers N``.

    On Unix this runs gunicorn with ``preload_app=True`` (the master builds the
    warm app once and forks workers via copy-on-write). ``max_requests`` controls
    worker recycling: ``None`` (the default) maps to ``DEFAULT_MAX_REQUESTS`` so warm
    workers recycle periodically and shed accumulated memory (with 10% jitter so they
    don't recycle in lockstep); ``0`` disables recycling; ``N`` recycles after N
    requests.

    **Isolation note.** ``--max-requests`` is worker hygiene, not per-request isolation:
    the async worker recycles gracefully, so a worker that has hit its limit keeps serving
    while it winds down and a later request can observe an earlier one's ``os.environ``
    writes. Strict isolation comes from ``--use-sync-workers`` (the blocking sync worker
    exits synchronously after each request) or ``--reset-environ`` (snapshot/restore
    ``os.environ`` around every run).

    gunicorn is Unix-only. On Windows it cannot run at all, so multi-worker serving
    falls back to uvicorn's own multi-worker supervisor (no preload, no recycling);
    ``--max-requests`` is refused there, since it cannot be supported.

    ``reset_environ`` (``--reset-environ``) is forwarded to the workers via
    ``LFX_SERVE_RESET_ENVIRON`` so each worker snapshots/restores ``os.environ``
    around every flow run (see ``guarded_execute``). ``sync_workers``
    (``--use-sync-workers``, Unix only) swaps the async worker for gunicorn's blocking
    ``sync`` worker wrapped by an a2wsgi ASGI->WSGI bridge, so the kernel routes each
    request to an idle worker. Both default off. ``timeout`` (``--timeout``) sets
    gunicorn's worker timeout; ``None`` maps to ``DEFAULT_TIMEOUT`` (120s) — raise it for
    long flows, especially under ``--use-sync-workers``.

    ``identity_config`` (``--identity-mode`` and friends) is round-tripped to the
    workers via ``LFX_SERVE_IDENTITY_*`` env vars so each worker reconstructs it in
    ``create_serve_app`` (uvicorn) or ``serve_preloaded_app`` (gunicorn preload).
    ``None`` means ``off`` (the default) — set explicitly so an inherited value
    can't silently flip it on.
    """
    from lfx.cli.serve_app import (
        _SERVE_FLOW_DIR_ENV,
        _SERVE_NO_ENV_FALLBACK_ENV,
        _SERVE_RESET_ENVIRON_ENV,
        _SERVE_STARTUP_PATHS_ENV,
    )
    from lfx.cli.serve_identity import IdentityConfig

    # Env vars each worker reads to reconstruct config: the gunicorn preload master via
    # build_registry_from_env(), or each uvicorn factory worker via create_serve_app().
    # When flow_dir is set, startup flows are already in the store (written by
    # _build_serve_registry) so workers load them via warm_from_store(); otherwise workers
    # re-read the original files from LFX_SERVE_STARTUP_PATHS.
    startup_paths_for_workers: list[str] = []
    if not flow_dir:
        if script_paths:
            startup_paths_for_workers = [str(Path(p).resolve()) for p in script_paths]
        elif temp_file_to_cleanup:
            startup_paths_for_workers = [temp_file_to_cleanup]
    worker_env = {
        _SERVE_FLOW_DIR_ENV: str(flow_dir) if flow_dir else "",
        _SERVE_NO_ENV_FALLBACK_ENV: "1" if no_env_fallback else "0",
        _SERVE_STARTUP_PATHS_ENV: json.dumps(startup_paths_for_workers),
        # Read per request by guarded_execute. Set explicitly (even "0") so a stray
        # inherited value can't silently flip behavior.
        _SERVE_RESET_ENVIRON_ENV: "1" if reset_environ else "0",
        # Round-trip identity config into the workers (each keeps its own JWKS cache — a
        # few KB; no cross-worker sharing). Set explicitly even for "off".
        **(identity_config or IdentityConfig()).to_env(),
    }

    with _exported_env(worker_env):
        if sys.platform == "win32":
            if max_requests is not None and max_requests > 0:
                typer.echo(
                    "Error: --max-requests enables gunicorn worker recycling, which is not "
                    "available on Windows. Omit --max-requests to run multi-worker on Windows. "
                    "For cross-request os.environ isolation use --reset-environ (any platform); "
                    "for per-process isolation deploy on Linux/macOS with --use-sync-workers.",
                    err=True,
                )
                raise typer.Exit(1)
            if sync_workers:
                typer.echo(
                    "Error: --use-sync-workers uses gunicorn's sync worker, which is not available on "
                    "Windows. Omit --use-sync-workers to run multi-worker on Windows, or deploy on "
                    "Linux/macOS for idle-worker routing.",
                    err=True,
                )
                raise typer.Exit(1)
            # gunicorn cannot run on Windows; fall back to uvicorn's multi-worker
            # supervisor. No preload/COW and no gunicorn recycling, though --reset-environ
            # still isolates per request (applied in guarded_execute, not gunicorn).
            verbose_print(
                "Note: multi-worker serving on Windows uses uvicorn (no gunicorn recycling); "
                "use --reset-environ for cross-request os.environ isolation, or deploy on "
                "Linux/macOS with --use-sync-workers for per-process isolation."
            )
            uvicorn.run(
                "lfx.cli.serve_app:create_serve_app",
                host=host,
                port=port,
                workers=workers,
                log_level=log_level,
                factory=True,
            )
        else:
            from lfx.cli.serve_gunicorn import LFXGunicornApp

            if sync_workers:
                # Fail fast in the parent rather than per-worker on first request. a2wsgi
                # ships with lfx on Linux/macOS, so a missing import means a broken
                # environment, not a forgotten optional install.
                try:
                    import a2wsgi  # noqa: F401
                except ImportError as exc:
                    typer.echo(
                        "Error: --use-sync-workers needs 'a2wsgi', which ships with lfx on Linux/macOS; "
                        "it is missing, so reinstall lfx to restore your environment.",
                        err=True,
                    )
                    raise typer.Exit(1) from exc
                # gunicorn's blocking sync worker stops accepting while a request runs,
                # so the kernel routes the next request to an idle worker. It serves the
                # ASGI app through the a2wsgi WSGI bridge (built lazily, post-fork).
                app_import_string = "lfx.cli.serve_preloaded_app:wsgi_application"
                worker_class = "sync"
            else:
                app_import_string = "lfx.cli.serve_preloaded_app:app"
                worker_class = "lfx.cli.serve_gunicorn.LFXUvicornWorker"

            # Unset (None) -> DEFAULT_MAX_REQUESTS so warm workers recycle periodically and
            # shed accumulated memory. Explicit 0 disables recycling; explicit N overrides.
            effective_max_requests = max_requests if max_requests is not None else DEFAULT_MAX_REQUESTS
            # Unset (None) -> DEFAULT_TIMEOUT; explicit --timeout N overrides.
            effective_timeout = timeout if timeout is not None else DEFAULT_TIMEOUT

            LFXGunicornApp(
                app_import_string,
                {
                    "bind": f"{host}:{port}",
                    "workers": workers,
                    "worker_class": worker_class,
                    "preload_app": True,
                    "max_requests": effective_max_requests,
                    # 10% jitter so workers don't all hit the limit on the same request count
                    # (avoids a synchronized recycle/latency blip). 0 stays 0 (never recycle).
                    "max_requests_jitter": effective_max_requests // 10,
                    "loglevel": log_level,
                    # Worker timeout (--timeout, default 120). gunicorn's own default is 30s,
                    # which would kill long LLM flows — especially under --use-sync-workers, where a
                    # blocking worker cannot heartbeat mid-request.
                    "timeout": effective_timeout,
                },
            ).run()


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
