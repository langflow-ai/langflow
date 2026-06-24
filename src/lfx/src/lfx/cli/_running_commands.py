"""Running commands: run, serve."""

import typer

from lfx.upgrade.cli_gate import UpgradeFlowMode


def register(app: typer.Typer) -> None:
    """Register running-stage commands on *app*."""

    @app.command(name="run", help="Run a flow directly", no_args_is_help=True, rich_help_panel="Running")
    def run_command_wrapper(
        script_path: str | None = typer.Argument(
            None, help="Path to the Python script (.py) or JSON flow (.json) containing a graph"
        ),
        input_value: str | None = typer.Argument(None, help="Input value to pass to the graph"),
        input_value_option: str | None = typer.Option(
            None,
            "--input-value",
            help="Input value to pass to the graph (alternative to positional argument)",
        ),
        output_format: str = typer.Option(
            "json",
            "--format",
            "-f",
            help="Output format: json, text, message, or result",
        ),
        flow_json: str | None = typer.Option(
            None,
            "--flow-json",
            help="Inline JSON flow content as a string (alternative to script_path)",
        ),
        *,
        stdin: bool = typer.Option(
            default=False,
            show_default=True,
            help="Read JSON flow content from stdin (alternative to script_path)",
        ),
        check_variables: bool = typer.Option(
            default=True,
            show_default=True,
            help="Check global variables for environment compatibility",
        ),
        check_dependencies: bool = typer.Option(
            default=True,
            show_default=True,
            help="Preflight the flow's required packages; fail fast with install guidance when any are missing",
        ),
        verbose: bool = typer.Option(
            False,
            "-v",
            "--verbose",
            help="Show basic progress information",
        ),
        verbose_detailed: bool = typer.Option(
            False,
            "-vv",
            help="Show detailed progress and debug information",
        ),
        verbose_full: bool = typer.Option(
            False,
            "-vvv",
            help="Show full debugging output including component logs",
        ),
        timing: bool = typer.Option(
            default=False,
            show_default=True,
            help="Include detailed timing information in output",
        ),
        session_id: str | None = typer.Option(
            None,
            "--session-id",
            help=(
                "Session ID to attach to the run. "
                "Agent and Memory Components will use this to track conversation history."
            ),
        ),
        upgrade_flow: UpgradeFlowMode | None = typer.Option(
            None,
            "--upgrade-flow",
            help=(
                "Component compatibility mode. "
                "'check' refuses to run if any component is outdated or blocked. "
                "'safe' auto-applies safe upgrades; aborts on breaking or blocked components."
            ),
        ),
    ) -> None:
        """Run a flow directly (lazy-loaded)."""
        from pathlib import Path

        from lfx.cli.run import run

        # Convert script_path string to Path if provided
        script_path_obj = Path(script_path) if script_path else None

        run(
            script_path=script_path_obj,
            input_value=input_value,
            input_value_option=input_value_option,
            output_format=output_format,
            flow_json=flow_json,
            stdin=stdin,
            check_variables=check_variables,
            check_dependencies=check_dependencies,
            verbose=verbose,
            verbose_detailed=verbose_detailed,
            verbose_full=verbose_full,
            timing=timing,
            session_id=session_id,
            upgrade_flow=upgrade_flow,
        )

    @app.command(name="serve", help="Serve a flow as an API", rich_help_panel="Running")
    def serve_command_wrapper(
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
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Show diagnostic output and execution details"),
        env_file: str | None = typer.Option(
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
        flow_dir: str | None = typer.Option(
            None,
            "--flow-dir",
            help=(
                "Directory for filesystem-backed flow storage. "
                "All uvicorn workers sharing this path will serve the same flows. "
                "Use /tmp/lfx-flows for single-pod sharing or a PVC mount for cross-pod. "
                "Defaults to in-memory only when omitted."
            ),
        ),
        max_requests: int | None = typer.Option(
            None,
            "--max-requests",
            help=(
                "Recycle each worker after this many requests (gunicorn, Unix-only, --workers > 1). "
                "Set to 1 for per-request worker recycling. Default (unset) means workers are never "
                "recycled. Not supported on Windows, where multi-worker serving uses uvicorn. "
                "For full per-request isolation, combine with --limit-concurrency 1."
            ),
        ),
        limit_concurrency: int | None = typer.Option(
            None,
            "--limit-concurrency",
            help=(
                "Max in-flight requests per worker (--workers > 1); excess get HTTP 503. "
                "Recycling alone does NOT stop a worker from accepting a 2nd concurrent request, so "
                "without this two requests may share one process/os.environ. Set to 1 (with "
                "--max-requests 1) so each worker handles exactly one request in its own process — "
                "strict cross-request isolation. Default (unset) means unlimited concurrency."
            ),
        ),
        timeout: int = typer.Option(
            120,
            "--timeout",
            help=(
                "Worker timeout in seconds (gunicorn, Unix, --workers > 1): a worker that does not "
                "complete a request within this many seconds is killed and restarted. Raise it for "
                "long-running flows, especially with --sync-workers (a blocking sync worker cannot "
                "heartbeat mid-request). Default: 120. No effect on Windows (uvicorn fallback)."
            ),
        ),
        *,
        stdin: bool = typer.Option(
            False,
            "--stdin",
            help="Read JSON flow content from stdin (alternative to script_paths)",
        ),
        check_variables: bool = typer.Option(
            True,
            "--check-variables/--no-check-variables",
            help="Check global variables for environment compatibility",
        ),
        upgrade_flow: UpgradeFlowMode | None = typer.Option(
            None,
            "--upgrade-flow",
            help=(
                "Component compatibility mode before serving. "
                "'check' refuses to serve if any component is outdated or blocked. "
                "'safe' auto-applies safe upgrades; aborts on breaking or blocked components."
            ),
        ),
        no_env_fallback: bool = typer.Option(
            False,
            "--no-env-fallback/--env-fallback",
            help=(
                "Disable os.environ fallback for credential variables. "
                "Variables not supplied via global_vars on each request resolve to None "
                "instead of reading from the process environment."
            ),
        ),
        reset_environ: bool = typer.Option(
            False,
            "--reset-environ/--no-reset-environ",
            help=(
                "Snapshot os.environ before each flow run and restore it afterward, so a "
                "flow's environment mutations (or request-scoped credentials) cannot leak "
                "into the next request served by the same warm worker. Off by default."
            ),
        ),
        sync_workers: bool = typer.Option(
            False,
            "--sync-workers/--no-sync-workers",
            help=(
                "Use gunicorn's blocking 'sync' worker (Unix, --workers > 1) so the kernel "
                "routes each request to an idle worker instead of queueing it behind an "
                "in-flight request on a busy async worker. Requires the 'a2wsgi' package. "
                "Off by default (async worker)."
            ),
        ),
        identity_mode: str = typer.Option(
            "off",
            "--identity-mode",
            help=(
                "Per-user identity forwarding mode. 'off' (default) ignores caller identity. "
                "'jwt' verifies a signed JWT (Authorization: Bearer or --identity-jwt-header) and "
                "threads its claim as user_id. 'header' trusts a plain gateway header verbatim "
                "(weaker; safe only when network policy guarantees the gateway is the sole caller)."
            ),
        ),
        identity_jwt_issuer: str | None = typer.Option(
            None,
            "--identity-jwt-issuer",
            help="Expected JWT 'iss' (exact match). Required when --identity-mode=jwt.",
        ),
        identity_jwt_audience: str | None = typer.Option(
            None,
            "--identity-jwt-audience",
            help="Expected JWT 'aud' (the token's audience must contain it). Required when --identity-mode=jwt.",
        ),
        identity_jwt_jwks_url: str | None = typer.Option(
            None,
            "--identity-jwt-jwks-url",
            help="JWKS URL for signing keys. Optional; defaults to OIDC discovery from the issuer.",
        ),
        identity_claim: str = typer.Option(
            "sub",
            "--identity-claim",
            help="JWT claim used as the caller identity (user_id). Defaults to 'sub'.",
        ),
        identity_jwt_header: str = typer.Option(
            "Authorization",
            "--identity-jwt-header",
            help="Header the JWT is read from in jwt mode (a 'Bearer ' prefix is stripped). Defaults to Authorization.",
        ),
        identity_header: str = typer.Option(
            "X-Consumer-Username",
            "--identity-header",
            help="Plain header trusted as identity in header mode. Defaults to X-Consumer-Username.",
        ),
        identity_jwt_allow_insecure_http: bool = typer.Option(
            False,
            "--identity-jwt-allow-insecure-http",
            help="Allow plaintext http:// for the JWKS/issuer (dev/test only). HTTPS is required by default.",
        ),
    ) -> None:
        """Serve LFX flows as a web API (lazy-loaded)."""
        from pathlib import Path

        from lfx.cli.commands import serve_command

        env_file_path = Path(env_file) if env_file else None
        flow_dir_path = Path(flow_dir) if flow_dir else None

        serve_command(
            script_paths=script_paths,
            host=host,
            port=port,
            workers=workers,
            verbose=verbose,
            env_file=env_file_path,
            log_level=log_level,
            flow_json=flow_json,
            flow_dir=flow_dir_path,
            stdin=stdin,
            check_variables=check_variables,
            upgrade_flow=upgrade_flow,
            no_env_fallback=no_env_fallback,
            max_requests=max_requests,
            limit_concurrency=limit_concurrency,
            reset_environ=reset_environ,
            sync_workers=sync_workers,
            timeout=timeout,
            identity_mode=identity_mode,
            identity_jwt_issuer=identity_jwt_issuer,
            identity_jwt_audience=identity_jwt_audience,
            identity_jwt_jwks_url=identity_jwt_jwks_url,
            identity_claim=identity_claim,
            identity_jwt_header=identity_jwt_header,
            identity_header=identity_header,
            identity_jwt_allow_insecure_http=identity_jwt_allow_insecure_http,
        )
