"""CLI wrapper for the run command."""

import json
import os
from functools import partial
from pathlib import Path

import typer
from asyncer import syncify
from dotenv import dotenv_values

from lfx.run.base import RunError, run_flow


def _parse_env_vars(env_vars: list[str] | None) -> dict[str, str]:
    """Parse KEY=VALUE pairs from CLI arguments."""
    result = {}
    if not env_vars:
        return result
    for item in env_vars:
        if "=" in item:
            key, value = item.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def _load_env_file(env_file: Path | None) -> dict[str, str]:
    """Load environment variables from .env file."""
    if not env_file or not env_file.exists():
        return {}
    return dict(dotenv_values(env_file))


# Verbosity level constants
VERBOSITY_DETAILED = 2
VERBOSITY_FULL = 3


def _check_langchain_version_compatibility(error_message: str) -> str | None:
    """Check if error is due to langchain-core version incompatibility.

    Returns a helpful error message if incompatibility is detected, None otherwise.
    """
    # Check for the specific error that occurs with langchain-core 1.x
    # The langchain_core.memory module was removed in langchain-core 1.x
    if "langchain_core.memory" in error_message or "No module named 'langchain_core.memory'" in error_message:
        try:
            import langchain_core

            version = getattr(langchain_core, "__version__", "unknown")
        except ImportError:
            version = "unknown"

        return (
            f"ERROR: Incompatible langchain-core version (v{version}).\n\n"
            "The 'langchain_core.memory' module was removed in langchain-core 1.x.\n"
            "lfx requires langchain-core < 1.0.0.\n\n"
            "This usually happens when langchain-openai >= 1.0.0 is installed,\n"
            "which pulls in langchain-core >= 1.0.0.\n\n"
            "FIX: Reinstall with compatible versions:\n\n"
            "  uv pip install 'langchain-core>=0.3.0,<1.0.0' \\\n"
            "                 'langchain-openai>=0.3.0,<1.0.0' \\\n"
            "                 'langchain-community>=0.3.0,<1.0.0'\n\n"
            "Or with pip:\n\n"
            "  pip install 'langchain-core>=0.3.0,<1.0.0' \\\n"
            "              'langchain-openai>=0.3.0,<1.0.0' \\\n"
            "              'langchain-community>=0.3.0,<1.0.0'"
        )
    return None


@partial(syncify, raise_sync_error=False)
async def run(
    script_path: Path | None = typer.Argument(  # noqa: B008
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
        help=("Inline JSON flow content as a string (alternative to script_path)"),
    ),
    project_path: Path | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Project folder containing subflows. Defaults to the directory of the flow file.",
    ),
    files_dir: Path | None = typer.Option(
        None,
        "--files-dir",
        "--files",
        help="Directory containing files referenced by the flow. Defaults to project path.",
    ),
    env_file: Path | None = typer.Option(
        None,
        "--env-file",
        help="Path to .env file with environment variables (e.g., OPENAI_API_KEY=sk-xxx)",
    ),
    env_vars: list[str] | None = typer.Option(
        None,
        "--env",
        "-e",
        help="Set environment variable as KEY=VALUE. Can be used multiple times.",
    ),
    *,
    stdin: bool | None = typer.Option(
        default=False,
        flag_value="--stdin",
        show_default=True,
        help="Read JSON flow content from stdin (alternative to script_path)",
    ),
    check_variables: bool = typer.Option(
        default=True,
        show_default=True,
        help="Check global variables for environment compatibility",
    ),
    verbose: bool = typer.Option(
        False,  # noqa: FBT003
        "-v",
        "--verbose",
        help="Show basic progress information",
    ),
    verbose_detailed: bool = typer.Option(
        False,  # noqa: FBT003
        "-vv",
        help="Show detailed progress and debug information",
    ),
    verbose_full: bool = typer.Option(
        False,  # noqa: FBT003
        "-vvv",
        help="Show full debugging output including component logs",
    ),
    timing: bool = typer.Option(
        default=False,
        show_default=True,
        help="Include detailed timing information in output",
    ),
) -> None:
    """Execute a Langflow graph script or JSON flow and return the result.

    This command analyzes and executes either a Python script containing a Langflow graph,
    a JSON flow file, inline JSON, or JSON from stdin, returning the result in the specified format.
    By default, output is minimal for use in containers and serverless environments.

    Args:
        script_path: Path to the Python script (.py) or JSON flow (.json) containing a graph
        input_value: Input value to pass to the graph (positional argument)
        input_value_option: Input value to pass to the graph (alternative option)
        verbose: Show diagnostic output and execution details
        verbose_detailed: Show detailed progress and debug information (-vv)
        verbose_full: Show full debugging output including component logs (-vvv)
        output_format: Format for output (json, text, message, or result)
        flow_json: Inline JSON flow content as a string
        stdin: Read JSON flow content from stdin
        check_variables: Check global variables for environment compatibility
        timing: Include detailed timing information in output
        project_path: Directory to search for subflows (defaults to flow file's directory)
        files_dir: Directory to resolve file paths (defaults to project_path)
        env_file: Path to .env file to load environment variables from
        env_vars: Environment variables in KEY=VALUE format
    """
    # Determine verbosity for output formatting
    verbosity = 3 if verbose_full else (2 if verbose_detailed else (1 if verbose else 0))

    # Determine project path: use provided path, or default to flow file's directory
    # Ensure project_path is a proper Path object (Typer may pass OptionInfo when None)
    resolved_project_path: Path | None = None
    if project_path is not None and isinstance(project_path, Path):
        resolved_project_path = project_path
    elif script_path is not None:
        resolved_project_path = script_path.parent

    # Determine files directory: use provided path, or default to project path
    resolved_files_dir = files_dir if files_dir is not None and isinstance(files_dir, Path) else resolved_project_path

    # Build global variables from env file and CLI args
    # Also set them in os.environ so components can access them directly
    global_variables: dict[str, str] = {}

    # Load from .env file first
    resolved_env_file = env_file if isinstance(env_file, Path) else None
    if resolved_env_file:
        global_variables.update(_load_env_file(resolved_env_file))

    # Override with CLI --env arguments
    global_variables.update(_parse_env_vars(env_vars))

    # Also set in os.environ for components that read directly from env
    for key, value in global_variables.items():
        os.environ[key] = value

    try:
        result = await run_flow(
            script_path=script_path,
            input_value=input_value,
            input_value_option=input_value_option,
            output_format=output_format,
            flow_json=flow_json,
            stdin=bool(stdin),
            check_variables=check_variables,
            verbose=verbose,
            verbose_detailed=verbose_detailed,
            verbose_full=verbose_full,
            timing=timing,
            global_variables=global_variables if global_variables else None,
            project_path=resolved_project_path,
            files_dir=resolved_files_dir,
        )

        # Output based on format
        if output_format in {"text", "message", "result"}:
            typer.echo(result.get("output", ""))
        else:
            indent = 2 if verbosity > 0 else None
            typer.echo(json.dumps(result, indent=indent))

    except RunError as e:
        error_response = {
            "success": False,
            "type": "error",
        }
        if e.original_exception:
            error_response["exception_type"] = type(e.original_exception).__name__
            error_response["exception_message"] = str(e.original_exception)
        else:
            error_response["exception_message"] = str(e)
        typer.echo(json.dumps(error_response))
        raise typer.Exit(1) from e
