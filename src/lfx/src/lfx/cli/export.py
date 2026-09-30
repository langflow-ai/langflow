"""lfx export -- serialize flows to git-friendly JSON.

Two modes of operation
----------------------
Local (default)
    Read one or more flow JSON files from disk, normalize them, and write the
    result back to disk (or stdout).  No network connection required.

Remote (--env / --flow-id / --project-id)
    Pull flows directly from a running Langflow instance using the
    ``langflow-sdk`` HTTP client, normalize them, and write to disk.

Examples:
--------
Normalize a local file in-place::

    lfx export my_flow.json --in-place

Normalize and write to a new file::

    lfx export my_flow.json -o my_flow.normalized.json

Pull a single flow from staging and write to the current directory::

    lfx export --flow-id <uuid> --env staging

Export an entire project from staging into ./flows/::

    lfx export --project-id <uuid> --env staging --output-dir ./flows/
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

import typer
from rich.console import Console

from lfx.cli.common import load_sdk, safe_filename

console = Console(stderr=True)


def _write_flow(
    flow: dict[str, Any],
    *,
    sdk: Any,
    output: Path | None,
    in_place: bool,
    source_path: Path | None,
    indent: int,
) -> Path | None:
    """Serialise *flow* and write it to the appropriate destination.

    Returns the path written to, or ``None`` if writing to stdout.
    """
    content = sdk.flow_to_json(flow, indent=indent)

    if in_place and source_path:
        source_path.write_text(content, encoding="utf-8")
        return source_path

    if output:
        output.write_text(content, encoding="utf-8")
        return output

    sys.stdout.write(content)
    return None


def export_command(
    flow_paths: list[str],
    *,
    output: str | None,
    output_dir: str | None,
    env: str | None,
    flow_id: str | None,
    project_id: str | None,
    environments_file: str | None,
    target: str | None = None,
    api_key: str | None = None,
    in_place: bool,
    strip_volatile: bool,
    strip_secrets: bool,
    code_as_lines: bool,
    strip_node_volatile: bool,
    indent: int,
) -> None:
    sdk = load_sdk("export")

    normalize_kwargs = {
        "strip_volatile": strip_volatile,
        "strip_secrets": strip_secrets,
        "sort_keys": True,
        "code_as_lines": code_as_lines,
        "strip_node_volatile": strip_node_volatile,
    }

    # ------------------------------------------------------------------
    # Remote mode: pull from a live Langflow instance
    # ------------------------------------------------------------------
    if flow_id or project_id:
        if not env and not target:
            console.print("[red]Error:[/red] --env or --target is required for remote export.")
            raise typer.Exit(1)

        from lfx.config import ConfigError, resolve_environment

        try:
            env_cfg = resolve_environment(
                env,
                target=target,
                api_key=api_key,
                environments_file=environments_file,
            )
        except ConfigError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1) from exc

        client = sdk.Client(base_url=env_cfg.url, api_key=env_cfg.api_key)

        if flow_id:
            flow_obj = client.get_flow(UUID(flow_id))
            normalized = sdk.normalize_flow(flow_obj.model_dump(mode="json"), **normalize_kwargs)
            dest_dir = Path(output_dir) if output_dir else Path.cwd()
            dest_dir.mkdir(parents=True, exist_ok=True)
            safe_name = safe_filename(flow_obj.name)
            out_path = dest_dir / f"{safe_name}.json"
            out_path.write_text(sdk.flow_to_json(normalized, indent=indent), encoding="utf-8")
            console.print(f"[green]Exported[/green] {flow_obj.name!r} → {out_path}")
            return

        # Project mode: export all flows
        project = client.get_project(UUID(project_id))
        dest_dir = Path(output_dir) if output_dir else Path.cwd() / safe_filename(project.name)
        dest_dir.mkdir(parents=True, exist_ok=True)

        exported = 0
        for flow_obj in project.flows:
            normalized = sdk.normalize_flow(flow_obj.model_dump(mode="json"), **normalize_kwargs)
            safe_name = safe_filename(flow_obj.name)
            out_path = dest_dir / f"{safe_name}.json"
            out_path.write_text(sdk.flow_to_json(normalized, indent=indent), encoding="utf-8")
            console.print(f"[green]Exported[/green] {flow_obj.name!r} → {out_path}")
            exported += 1

        console.print(f"\n[bold]{exported}[/bold] flow(s) exported to {dest_dir}")
        return

    # ------------------------------------------------------------------
    # Local mode: normalize files already on disk
    # ------------------------------------------------------------------
    if not flow_paths:
        console.print("[red]Error:[/red] Provide at least one flow JSON file, or use --flow-id / --project-id.")
        raise typer.Exit(1)

    if output and len(flow_paths) > 1:
        console.print("[red]Error:[/red] --output can only be used with a single input file.")
        raise typer.Exit(1)

    out_path_obj = Path(output) if output else None

    for raw_path in flow_paths:
        src = Path(raw_path)
        if not src.exists():
            console.print(f"[red]Error:[/red] File not found: {src}")
            raise typer.Exit(1)

        try:
            normalized = sdk.normalize_flow_file(src, **normalize_kwargs)
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            console.print(f"[red]Error:[/red] Could not process {src}: {exc}")
            raise typer.Exit(1) from exc

        dest = _write_flow(
            normalized,
            sdk=sdk,
            output=out_path_obj,
            in_place=in_place,
            source_path=src,
            indent=indent,
        )
        if dest:
            console.print(f"[green]Exported[/green] {src} → {dest}")
