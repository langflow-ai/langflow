"""lfx pull -- fetch flows from a remote Langflow instance to local files.

Downloads flows from a live Langflow instance, normalizes them for version
control, and writes them to a local directory.  Repeated pulls are safe:
existing files are overwritten with the latest remote state.

Usage examples
--------------
Pull all flows from staging to ``flows/``::

    lfx pull --env staging

Pull all flows in a named project::

    lfx pull --env staging --project "My RAG Pipeline"

Pull a single flow by UUID::

    lfx pull --env staging --flow-id <uuid>

Pull to a custom directory::

    lfx pull --env production --output-dir ./local-flows/
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from lfx.cli.common import load_sdk, safe_filename
from lfx.log.logger import logger

console = Console(stderr=True)
ok_console = Console()


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class PullResult:
    flow_id: UUID
    flow_name: str
    path: Path
    status: str  # "unchanged" | "updated" | "created" | "error"
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status != "error"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_flow(
    flow_obj: Any,
    *,
    sdk: Any,
    dest_dir: Path,
    strip_secrets: bool,
    indent: int,
) -> PullResult:
    """Normalize and write a single flow to *dest_dir*."""
    flow_id = flow_obj.id
    flow_name = flow_obj.name

    try:
        normalized = sdk.normalize_flow(
            flow_obj.model_dump(mode="json"),
            strip_volatile=True,
            strip_secrets=strip_secrets,
            sort_keys=True,
        )
        safe_name = safe_filename(flow_name)
        out_path = dest_dir / f"{safe_name}.json"
        new_content = sdk.flow_to_json(normalized, indent=indent)
        if out_path.exists() and out_path.read_text(encoding="utf-8") == new_content:
            status = "unchanged"
        else:
            status = "created" if not out_path.exists() else "updated"
            out_path.write_text(new_content, encoding="utf-8")
        return PullResult(flow_id=flow_id, flow_name=flow_name, path=out_path, status=status)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to write flow %s", flow_id, exc_info=True)
        dummy_path = dest_dir / f"{flow_id}.json"
        return PullResult(flow_id=flow_id, flow_name=flow_name, path=dummy_path, status="error", error=str(exc))


def _render_results(results: list[PullResult]) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("Name")
    table.add_column("ID")
    table.add_column("File")
    table.add_column("Status")

    status_style = {
        "unchanged": ("dim", "UNCHANGED"),
        "updated": ("yellow", "UPDATED"),
        "created": ("green", "CREATED"),
        "error": ("red", "ERROR"),
    }

    for r in results:
        color, label = status_style.get(r.status, ("white", r.status.upper()))
        if r.error:
            label += f": {r.error}"
        table.add_row(r.flow_name, str(r.flow_id), str(r.path), f"[{color}]{label}[/{color}]")

    ok_console.print()
    ok_console.print(table)

    errors = [r for r in results if not r.ok]
    n_changed = sum(1 for r in results if r.status in ("created", "updated"))
    n_unchanged = sum(1 for r in results if r.status == "unchanged")
    if errors:
        console.print(f"\n[red]{len(errors)} pull(s) failed.[/red]")
    else:
        parts = []
        if n_changed:
            parts.append(f"[green]{n_changed} updated[/green]")
        if n_unchanged:
            parts.append(f"[dim]{n_unchanged} unchanged[/dim]")
        ok_console.print("\n" + ", ".join(parts) + ".")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def pull_command(
    *,
    env: str | None,
    output_dir: str | None,
    flow_id: str | None,
    project: str | None,
    project_id: str | None,
    environments_file: str | None,
    target: str | None = None,
    api_key: str | None = None,
    strip_secrets: bool,
    indent: int,
) -> None:
    sdk = load_sdk("pull")

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

    dest_dir = Path(output_dir) if output_dir else Path("flows")
    dest_dir.mkdir(parents=True, exist_ok=True)

    results: list[PullResult] = []

    # ---- Single flow by ID -----------------------------------------------
    if flow_id:
        try:
            flow_obj = client.get_flow(UUID(flow_id))
        except Exception as exc:
            console.print(f"[red]Error:[/red] Could not fetch flow {flow_id}: {exc}")
            raise typer.Exit(1) from exc

        result = _write_flow(flow_obj, sdk=sdk, dest_dir=dest_dir, strip_secrets=strip_secrets, indent=indent)
        results.append(result)
        if result.ok:
            console.print(f"[green]Pulled[/green] {result.flow_name!r} → {result.path}")
        else:
            console.print(f"[red]Failed[/red] {result.flow_name!r}: {result.error}")

    # ---- All flows in a named project ------------------------------------
    elif project or project_id:
        if project_id:
            try:
                proj = client.get_project(UUID(project_id))
            except Exception as exc:
                console.print(f"[red]Error:[/red] Could not fetch project {project_id}: {exc}")
                raise typer.Exit(1) from exc
        else:
            projects = client.list_projects()
            matched = [p for p in projects if p.name == project]
            if not matched:
                names = ", ".join(repr(p.name) for p in projects) or "(none)"
                console.print(f"[red]Error:[/red] Project {project!r} not found. Available: {names}")
                raise typer.Exit(1)
            try:
                proj = client.get_project(matched[0].id)
            except Exception as exc:
                console.print(f"[red]Error:[/red] Could not fetch project {project!r}: {exc}")
                raise typer.Exit(1) from exc

        console.print(f"[dim]Pulling from project[/dim] {proj.name!r} (id={proj.id})")

        for flow_obj in proj.flows:
            result = _write_flow(flow_obj, sdk=sdk, dest_dir=dest_dir, strip_secrets=strip_secrets, indent=indent)
            results.append(result)
            if result.status == "unchanged":
                console.print(f"[dim]Unchanged[/dim] {result.flow_name!r}")
            elif result.ok:
                console.print(f"[green]Pulled[/green] {result.flow_name!r} → {result.path}")
            else:
                console.print(f"[red]Failed[/red] {result.flow_name!r}: {result.error}")

    # ---- All flows in the environment ------------------------------------
    else:
        console.print(f"[dim]Pulling all flows from[/dim] {env_cfg.url}")
        try:
            flows = client.list_flows(get_all=True, remove_example_flows=True)
        except Exception as exc:
            console.print(f"[red]Error:[/red] Could not list flows: {exc}")
            raise typer.Exit(1) from exc

        if not flows:
            console.print("[yellow]Warning:[/yellow] No flows found on the remote instance.")
            return

        for flow_obj in flows:
            result = _write_flow(flow_obj, sdk=sdk, dest_dir=dest_dir, strip_secrets=strip_secrets, indent=indent)
            results.append(result)
            if result.status == "unchanged":
                console.print(f"[dim]Unchanged[/dim] {result.flow_name!r}")
            elif result.ok:
                console.print(f"[green]Pulled[/green] {result.flow_name!r} → {result.path}")
            else:
                console.print(f"[red]Failed[/red] {result.flow_name!r}: {result.error}")

    _render_results(results)

    if any(not r.ok for r in results):
        raise typer.Exit(1)
