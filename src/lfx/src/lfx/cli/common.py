"""Common utilities for LFX CLI commands."""

from __future__ import annotations

import os
import socket
import sys
import uuid
from typing import TYPE_CHECKING, Any

import typer
from loguru import logger

from lfx.load import load_flow_from_json

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from lfx.graph import Graph

MAX_PORT_NUMBER = 65535

# Fixed namespace constant for deterministic UUID5 generation across runs
_LANGFLOW_NAMESPACE_UUID = uuid.UUID("3c091057-e799-4e32-8ebc-27bc31e1108c")


def create_verbose_printer(*, verbose: bool) -> Callable[[str], None]:
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


def is_port_in_use(port: int, host: str = "localhost") -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
        except OSError:
            return True
        else:
            return False


def get_free_port(starting_port: int = 8000) -> int:
    """Get a free port starting from the given port."""
    port = starting_port
    while port < MAX_PORT_NUMBER:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
            except OSError:
                port += 1
            else:
                return port
    msg = "No free ports available"
    raise RuntimeError(msg)


def get_best_access_host(host: str) -> str:
    """Determine the best host to display for access URLs.

    For binding addresses like 0.0.0.0 or empty string, returns a more
    user-friendly address for display purposes.
    """
    if host in {"0.0.0.0", ""}:
        return "localhost"
    return host


def get_api_key() -> str:
    """Get the API key from environment variables.

    Returns:
        str: The API key

    Raises:
        ValueError: If LANGFLOW_API_KEY is not set
    """
    api_key = os.getenv("LANGFLOW_API_KEY")
    if not api_key:
        msg = "LANGFLOW_API_KEY environment variable is not set"
        raise ValueError(msg)
    return api_key


def flow_id_from_path(path: Path, root_dir: Path) -> str:
    """Generate a deterministic flow ID from a file path.

    Uses UUID5 with a fixed namespace to ensure the same path always
    generates the same ID across different runs.
    """
    relative_path = path.relative_to(root_dir)
    return str(uuid.uuid5(_LANGFLOW_NAMESPACE_UUID, str(relative_path)))


def load_graph_from_path(
    path: Path,
    verbose_print: Callable[[str], None],
    *,
    verbose: bool = False,
) -> Graph:
    """Load a graph from a JSON file.

    Args:
        path: Path to the JSON file
        verbose_print: Function for printing verbose output
        verbose: Whether to show verbose output

    Returns:
        Graph: The loaded graph object

    Raises:
        typer.Exit: If loading fails
    """
    try:
        verbose_print(f"Loading flow from: {path}")

        # Load the flow from JSON
        flow_graph = load_flow_from_json(flow=str(path))

        if verbose:
            verbose_print(f"✓ Successfully loaded flow with {len(flow_graph.nodes)} nodes")

    except Exception as e:
        verbose_print(f"✗ Failed to load flow from {path}: {e}")
        raise typer.Exit(1) from e
    else:
        return flow_graph


async def execute_graph_with_capture(
    graph: Graph,
    input_value: str,
) -> tuple[list[Any], str]:
    """Execute a graph and capture the results and logs.

    Args:
        graph: The graph to execute
        input_value: Input value for the graph

    Returns:
        tuple: (results, logs) where results is a list of outputs and logs is captured output
    """
    from io import StringIO

    # Capture logs
    log_buffer = StringIO()

    try:
        # Execute the graph
        from lfx.schema.schema import InputValueRequest

        inputs = [InputValueRequest(components=[], input_value=input_value)]

        # Run the graph
        outputs = await graph.arun(
            inputs=inputs,
            outputs=[],
            stream=False,
        )

        # Extract results
        results = []
        for output in outputs:
            if hasattr(output, "outputs"):
                for out in output.outputs:
                    if hasattr(out, "results"):
                        results.append(out.results)
                    elif hasattr(out, "message"):
                        results.append({"text": out.message.text})
                    else:
                        results.append({"text": str(out)})

        logs = log_buffer.getvalue()

    except Exception as e:  # noqa: BLE001
        logger.error(f"Error executing graph: {e}")
        logs = log_buffer.getvalue()
        return [], f"ERROR: {e!s}\n{logs}"
    else:
        return results, logs


def extract_result_data(results: list[Any], logs: str) -> dict[str, Any]:  # noqa: ARG001
    """Extract result data from graph execution results.

    Args:
        results: List of results from graph execution
        logs: Captured logs

    Returns:
        dict: Formatted result data
    """
    if not results:
        return {
            "result": "No output generated",
            "success": False,
            "type": "error",
            "component": "",
        }

    # Get the last result
    last_result = results[-1]

    if isinstance(last_result, dict):
        text = last_result.get("text", "")
        return {
            "result": text,
            "text": text,
            "success": True,
            "type": "message",
            "component": last_result.get("component", ""),
        }
    return {
        "result": str(last_result),
        "text": str(last_result),
        "success": True,
        "type": "message",
        "component": "",
    }
