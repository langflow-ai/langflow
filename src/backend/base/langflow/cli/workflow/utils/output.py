"""Output formatting utilities for Genesis CLI."""

from typing import List, Dict, Any
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


console = Console()


def success_message(message: str):
    """Display a success message."""
    click.echo(click.style(f"✅ {message}", fg="green"))


def error_message(message: str):
    """Display an error message."""
    click.echo(click.style(f"❌ {message}", fg="red"), err=True)


def warning_message(message: str):
    """Display a warning message."""
    click.echo(click.style(f"⚠️  {message}", fg="yellow"))


def info_message(message: str):
    """Display an info message."""
    click.echo(click.style(f"ℹ️  {message}", fg="blue"))


def format_table(headers: List[str], rows: List[List[str]], title: str = None) -> str:
    """Format data as a table using Rich."""
    table = Table(title=title)

    # Add columns
    for header in headers:
        table.add_column(header, style="cyan", no_wrap=True)

    # Add rows
    for row in rows:
        table.add_row(*row)

    # Capture table output
    with console.capture() as capture:
        console.print(table)

    return capture.get()


def format_panel(content: str, title: str = None, style: str = "blue") -> str:
    """Format content as a panel using Rich."""
    panel = Panel(content, title=title, border_style=style)

    with console.capture() as capture:
        console.print(panel)

    return capture.get()


def format_validation_report(result: Dict[str, Any]) -> str:
    """Format validation results as a readable report."""
    lines = []

    # Header
    valid = result.get("valid", False)
    status = "✅ VALID" if valid else "❌ INVALID"
    lines.append(f"Specification Validation Report")
    lines.append("=" * 40)
    lines.append(f"Status: {status}")
    lines.append("")

    # Summary
    summary = result.get("summary", {})
    if summary:
        lines.append("Summary:")
        lines.append(f"  Errors: {summary.get('error_count', 0)}")
        lines.append(f"  Warnings: {summary.get('warning_count', 0)}")
        lines.append(f"  Suggestions: {summary.get('suggestion_count', 0)}")
        lines.append("")

    # Validation phases
    phases = result.get("validation_phases", {})
    if phases:
        lines.append("Validation Phases:")
        for phase, passed in phases.items():
            if passed is not None:
                status_icon = "✅" if passed else "❌"
                phase_name = phase.replace("_", " ").title()
                lines.append(f"  {status_icon} {phase_name}")
        lines.append("")

    # Errors
    errors = result.get("errors", [])
    if errors:
        lines.append("Errors:")
        for error in errors:
            if isinstance(error, dict):
                message = error.get("message", str(error))
                component = error.get("component_id", "")
                field = error.get("field", "")
                location = f" ({component}.{field})" if component and field else f" ({component})" if component else ""
                lines.append(f"  ❌ {message}{location}")
            else:
                lines.append(f"  ❌ {error}")
        lines.append("")

    # Warnings
    warnings = result.get("warnings", [])
    if warnings:
        lines.append("Warnings:")
        for warning in warnings:
            if isinstance(warning, dict):
                message = warning.get("message", str(warning))
                component = warning.get("component_id", "")
                lines.append(f"  ⚠️  {message}" + (f" ({component})" if component else ""))
            else:
                lines.append(f"  ⚠️  {warning}")
        lines.append("")

    # Suggestions
    suggestions = result.get("suggestions", [])
    actionable = result.get("actionable_suggestions", [])

    if suggestions or actionable:
        lines.append("Suggestions:")
        for suggestion in suggestions:
            if isinstance(suggestion, dict):
                message = suggestion.get("message", str(suggestion))
                lines.append(f"  💡 {message}")
            else:
                lines.append(f"  💡 {suggestion}")

        for suggestion in actionable:
            lines.append(f"  💡 {suggestion}")

    return "\n".join(lines)


def format_flow_stats(flow: Dict[str, Any]) -> str:
    """Format flow statistics for display."""
    data = flow.get("data", {})
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    lines = []
    lines.append("Flow Statistics:")
    lines.append(f"  Nodes: {len(nodes)}")
    lines.append(f"  Edges: {len(edges)}")

    # Node type breakdown
    node_types = {}
    for node in nodes:
        node_type = node.get("data", {}).get("type", "Unknown")
        node_types[node_type] = node_types.get(node_type, 0) + 1

    if node_types:
        lines.append("  Node Types:")
        for node_type, count in sorted(node_types.items()):
            lines.append(f"    {node_type}: {count}")

    return "\n".join(lines)