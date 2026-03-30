"""lfx create -- scaffold a new flow JSON from a built-in template.

Writes a ready-to-edit flow JSON file into the target directory so teams
can start from a known-good structure rather than an empty file.

Examples::

    lfx create my-chatbot
    lfx create my-rag --template hello-world
    lfx create my-flow --output-dir ./flows --overwrite
    lfx create --list
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

console = Console()

_FLOWS_TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "flows"

# Descriptions shown in ``lfx create --list``
_TEMPLATE_DESCRIPTIONS: dict[str, str] = {
    "hello-world": "ChatInput → ChatOutput — minimal echo flow, no LLM required",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def list_templates() -> list[str]:
    """Return the names of all available flow templates (sorted)."""
    if not _FLOWS_TEMPLATE_DIR.exists():
        return []
    return sorted(p.stem for p in _FLOWS_TEMPLATE_DIR.glob("*.json"))


def _load_template(name: str) -> dict[str, Any]:
    """Load and parse a template JSON by name.  Raises FileNotFoundError if missing."""
    path = _FLOWS_TEMPLATE_DIR / f"{name}.json"
    if not path.exists():
        available = list_templates()
        hint = f"  Available templates: {', '.join(available)}" if available else "  No templates found."
        msg = f"Template '{name}' not found.\n{hint}"
        raise FileNotFoundError(msg)
    return json.loads(path.read_text(encoding="utf-8"))


def _slugify(name: str) -> str:
    """Convert a flow name to a safe filename stem (lowercase, hyphens)."""
    return name.lower().replace(" ", "-").replace("_", "-")


# ---------------------------------------------------------------------------
# Core command (importable for testing and for init seeding)
# ---------------------------------------------------------------------------


def create_command(
    name: str,
    *,
    template: str = "hello-world",
    output_dir: Path = Path("flows"),
    overwrite: bool = False,
) -> Path:
    """Create a new flow JSON from *template* and write it to *output_dir/<slug>.json*.

    Returns the path of the written file.
    Raises ``typer.Exit`` on user-facing errors so the CLI reports them cleanly.
    """
    available = list_templates()
    if not available:
        console.print("[red]Error:[/red] No flow templates found in the lfx package.")
        raise typer.Exit(1)

    if template not in available:
        console.print(
            f"[red]Error:[/red] Unknown template [bold]{template!r}[/bold]. Available: {', '.join(available)}"
        )
        raise typer.Exit(1)

    slug = _slugify(name)
    output_dir = output_dir.resolve()
    dest = output_dir / f"{slug}.json"

    if dest.exists() and not overwrite:
        console.print(f"[red]Error:[/red] {dest} already exists. Use [bold]--overwrite[/bold] to replace it.")
        raise typer.Exit(1)

    # Load template and stamp with a fresh UUID + the requested name
    flow = _load_template(template)
    flow["id"] = str(uuid.uuid4())
    flow["name"] = name

    output_dir.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(flow, indent=2), encoding="utf-8")

    console.print(f"[bold green]✓[/bold green] Created [bold]{dest}[/bold]")
    console.print(f"  Template : {template}")
    console.print(f"  Flow ID  : {flow['id']}")
    console.print()
    console.print("Next steps:")
    console.print(f"  [bold]lfx validate {dest}[/bold]")
    console.print(f"  [bold]lfx serve {dest}[/bold]")

    return dest


# ---------------------------------------------------------------------------
# Listing helper (also used by the CLI --list flag)
# ---------------------------------------------------------------------------


def print_templates() -> None:
    """Print available templates as a Rich table."""
    available = list_templates()
    if not available:
        console.print("[yellow]No flow templates found.[/yellow]")
        return

    table = Table(title="Available flow templates", show_header=True, header_style="bold")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description")

    for name in available:
        desc = _TEMPLATE_DESCRIPTIONS.get(name, "")
        table.add_row(name, desc)

    console.print(table)
