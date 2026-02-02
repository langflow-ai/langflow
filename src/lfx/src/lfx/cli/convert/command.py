"""CLI command for JSON to Python flow conversion."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from .generator import generate_python_code
from .parsing import parse_flow_json

console = Console()


def convert_flow_to_python(flow_path: Path) -> str:
    """Convert a flow JSON file to Python code.

    Args:
        flow_path: Path to the Langflow JSON flow file.

    Returns:
        Generated Python code as a string.
    """
    flow_info = parse_flow_json(flow_path)
    return generate_python_code(flow_info)


def convert_command(
    flow_json: Path = typer.Argument(
        ...,
        help="Path to the Langflow JSON flow file",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    output: Path | None = typer.Option(
        None,
        "-o",
        "--output",
        help="Output Python file (default: stdout)",
    ),
    quiet: bool = typer.Option(
        False,  # noqa: FBT003
        "-q",
        "--quiet",
        help="Suppress informational messages",
    ),
) -> None:
    """Convert a Langflow JSON flow to Python code.

    This command converts JSON flow definitions exported from the Langflow UI
    into Python code that can be version-controlled and maintained as code.

    The generated Python code includes:

    - Component imports from lfx

    - Custom component class definitions (if any)

    - Prompt constants (extracted from long text fields)

    - A build_*_graph() function that constructs the flow

    - Connection setup via .set() method calls

    Examples:

        lfx convert my_flow.json                    # Output to stdout

        lfx convert my_flow.json -o my_flow.py     # Output to file

        lfx convert flow.json | ruff format -      # Format with ruff
    """
    try:
        python_code = convert_flow_to_python(flow_json)

        if output:
            output.write_text(python_code)
            if not quiet:
                flow_info = parse_flow_json(flow_json)
                console.print(f"[green]✓[/green] Converted: {flow_json.name}")
                console.print(f"  [dim]Nodes:[/dim] {len(flow_info.nodes)}")
                console.print(f"  [dim]Edges:[/dim] {len(flow_info.edges)}")
                console.print(f"  [dim]Prompts extracted:[/dim] {len(flow_info.prompts)}")
                console.print(f"  [dim]Output:[/dim] {output}")
        else:
            typer.echo(python_code)

    except json.JSONDecodeError as e:
        console.print(f"[red]Error:[/red] Invalid JSON: {e}", err=True)
        raise typer.Exit(1) from e
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] File not found: {e}", err=True)
        raise typer.Exit(1) from e
