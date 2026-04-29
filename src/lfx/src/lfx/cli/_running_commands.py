"""Running commands: run, serve."""

import typer


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
                "Session ID to attach to the run. Agent and Memory Components will use this to track conversation history."
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
            verbose=verbose,
            verbose_detailed=verbose_detailed,
            verbose_full=verbose_full,
            timing=timing,
            session_id=session_id,
        )

    @app.command(name="serve", help="Serve a flow as an API", no_args_is_help=True, rich_help_panel="Running")
    def serve_command_wrapper(
        script_path: str | None = typer.Argument(
            None,
            help=(
                "Path to JSON flow (.json) or Python script (.py) file or stdin input. "
                "Optional when using --flow-json or --stdin."
            ),
        ),
        host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind the server to"),
        port: int = typer.Option(8000, "--port", "-p", help="Port to bind the server to"),
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
            help="Inline JSON flow content as a string (alternative to script_path)",
        ),
        *,
        stdin: bool = typer.Option(
            False,
            "--stdin",
            help="Read JSON flow content from stdin (alternative to script_path)",
        ),
        check_variables: bool = typer.Option(
            True,
            "--check-variables/--no-check-variables",
            help="Check global variables for environment compatibility",
        ),
    ) -> None:
        """Serve LFX flows as a web API (lazy-loaded)."""
        from pathlib import Path

        from lfx.cli.commands import serve_command

        # Convert env_file string to Path if provided
        env_file_path = Path(env_file) if env_file else None

        serve_command(
            script_path=script_path,
            host=host,
            port=port,
            verbose=verbose,
            env_file=env_file_path,
            log_level=log_level,
            flow_json=flow_json,
            stdin=stdin,
            check_variables=check_variables,
        )
