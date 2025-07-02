"""Common utilities for CLI commands."""

import sys
from io import StringIO
from pathlib import Path

import typer

from langflow.api.v1.schemas import InputValueRequest
from langflow.cli.script_loader import (
    extract_structured_result,
    find_graph_variable,
    load_graph_from_script,
)
from langflow.load import load_flow_from_json


def create_verbose_printer(*, verbose: bool):
    """Create a verbose printer function that only prints in verbose mode.

    Args:
        verbose: Whether to print verbose output

    Returns:
        Function that prints to stderr only in verbose mode
    """

    def verbose_print(message: str) -> None:
        """Print diagnostic messages to stderr only in verbose mode."""
        if verbose:
            typer.echo(message, file=sys.stderr)

    return verbose_print


def validate_script_path(script_path: Path, verbose_print) -> str:
    """Validate script path and return file extension.

    Args:
        script_path: Path to the script file
        verbose_print: Function to print verbose messages

    Returns:
        File extension (.py or .json)

    Raises:
        typer.Exit: If validation fails
    """
    if not script_path.exists():
        verbose_print(f"Error: File '{script_path}' does not exist.")
        raise typer.Exit(1)

    if not script_path.is_file():
        verbose_print(f"Error: '{script_path}' is not a file.")
        raise typer.Exit(1)

    # Check file extension and validate
    file_extension = script_path.suffix.lower()
    if file_extension not in [".py", ".json"]:
        verbose_print(f"Error: '{script_path}' must be a .py or .json file.")
        raise typer.Exit(1)

    return file_extension


def load_graph_from_path(script_path: Path, file_extension: str, verbose_print, *, verbose: bool = False):
    """Load a graph from a Python script or JSON file.

    Args:
        script_path: Path to the script file
        file_extension: File extension (.py or .json)
        verbose_print: Function to print verbose messages
        verbose: Whether verbose mode is enabled

    Returns:
        Loaded graph object

    Raises:
        typer.Exit: If loading fails
    """
    file_type = "Python script" if file_extension == ".py" else "JSON flow"
    verbose_print(f"Analyzing {file_type}: {script_path}")

    try:
        if file_extension == ".py":
            verbose_print("Analyzing Python script...")
            graph_var = find_graph_variable(script_path)
            if graph_var:
                source_info = graph_var.get("source", "Unknown")
                type_info = graph_var.get("type", "Unknown")
                line_no = graph_var.get("line", "Unknown")
                verbose_print(f"✓ Found 'graph' variable at line {line_no}")
                verbose_print(f"  Type: {type_info}")
                verbose_print(f"  Source: {source_info}")
            else:
                error_msg = "No 'graph' variable found in script"
                verbose_print(f"✗ {error_msg}")
                raise ValueError(error_msg)

            verbose_print("Loading graph...")
            graph = load_graph_from_script(script_path)
        else:  # .json
            verbose_print("Loading JSON flow...")
            graph = load_flow_from_json(script_path, disable_logs=not verbose)

    except ValueError as e:
        # Re-raise ValueError as typer.Exit to preserve the error message
        raise typer.Exit(1) from e
    except Exception as e:
        verbose_print(f"✗ Failed to load graph: {e}")
        raise typer.Exit(1) from e
    else:
        return graph


def prepare_graph(graph, verbose_print):
    """Prepare a graph for execution.

    Args:
        graph: Graph object to prepare
        verbose_print: Function to print verbose messages

    Raises:
        typer.Exit: If preparation fails
    """
    verbose_print("Preparing graph for execution...")
    try:
        graph.prepare()
        verbose_print("✓ Graph prepared successfully")
    except Exception as e:
        verbose_print(f"✗ Failed to prepare graph: {e}")
        raise typer.Exit(1) from e


def execute_graph_with_capture(graph, input_value: str | None):
    """Execute a graph and capture output.

    Args:
        graph: Graph object to execute
        input_value: Input value to pass to the graph

    Returns:
        Tuple of (results, captured_logs)
    """
    # Create input request
    inputs = InputValueRequest(input_value=input_value) if input_value else None

    # Capture output during execution
    captured_stdout = StringIO()
    captured_stderr = StringIO()

    # Redirect stdout and stderr during graph execution
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    try:
        sys.stdout = captured_stdout
        sys.stderr = captured_stderr
        results = list(graph.start(inputs))
    finally:
        # Restore original stdout/stderr
        sys.stdout = original_stdout
        sys.stderr = original_stderr

    # Get captured logs
    captured_logs = captured_stdout.getvalue() + captured_stderr.getvalue()

    return results, captured_logs


def extract_result_data(results, captured_logs: str) -> dict:
    """Extract structured result data from graph execution results.

    Args:
        results: Graph execution results
        captured_logs: Captured output logs

    Returns:
        Structured result data dictionary
    """
    result_data = extract_structured_result(results)
    result_data["logs"] = captured_logs
    return result_data
