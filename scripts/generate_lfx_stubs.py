#!/usr/bin/env python
"""Generate .pyi stub files for lfx components.

This script generates type stubs for all lfx components, enabling:
- Autocomplete for set() method parameters in VSCode/PyCharm
- Type hints for output methods
- Better IDE integration when building flows from Python

Usage:
    python scripts/generate_lfx_stubs.py [--inline | output_dir]

Examples:
    # Generate inline stubs (directly in the lfx package for distribution)
    python scripts/generate_lfx_stubs.py --inline

    # Generate stubs to typings/ folder (for local development)
    python scripts/generate_lfx_stubs.py

    # Generate stubs to custom location
    python scripts/generate_lfx_stubs.py ./my-stubs
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add lfx to path so we can import it
lfx_path = Path(__file__).parent.parent / "src" / "lfx" / "src"
sys.path.insert(0, str(lfx_path))


def main():
    from lfx.stubs import generate_stubs
    from rich.console import Console

    console = Console()

    # Check for --inline flag
    inline_mode = "--inline" in sys.argv

    if inline_mode:
        # Generate stubs directly in the lfx package (for distribution)
        output_dir = Path(__file__).parent.parent / "src" / "lfx" / "src"
        console.print("[bold]Generating inline stubs (for package distribution)[/bold]")
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        output_dir = Path(sys.argv[1])
    else:
        # Default: typings/ in repo root (for local VSCode development)
        output_dir = Path(__file__).parent.parent / "typings"

    console.print(f"[bold]Output directory: {output_dir}[/bold]")

    stubs = generate_stubs(output_dir)

    console.print(f"[green]Generated {len(stubs)} stub files[/green]")

    max_display = 10
    for stub_path in sorted(stubs.keys())[:max_display]:
        console.print(f"  - {stub_path}")

    if len(stubs) > max_display:
        console.print(f"  ... and {len(stubs) - max_display} more")

    console.print()
    if inline_mode:
        console.print("[dim]Stubs are now part of the lfx package.[/dim]")
        console.print("[dim]Users will get autocomplete when they 'pip install lfx'.[/dim]")
    else:
        console.print("[dim]VSCode should automatically pick up stubs from 'typings/' folder.[/dim]")
        console.print("[dim]If not, add to .vscode/settings.json:[/dim]")
        console.print('[blue]  "python.analysis.stubPath": "typings"[/blue]')


if __name__ == "__main__":
    main()
