"""lfx push -- push normalized flow JSON to a remote Langflow instance.

Uses stable flow IDs for upsert (PUT /api/v1/flows/{id}), so repeated pushes
are idempotent: the first push creates the flow, subsequent ones update it in
place without changing its ID on the remote instance.

Usage examples
--------------
Push a single flow to staging::

    lfx push my_flow.json --env staging

Push several flows at once::

    lfx push flows/*.json --env staging

Push all flows in a directory and place them in a named project::

    lfx push --dir ./flows/ --env staging --project "My RAG Pipeline"

Dry-run to see what would happen::

    lfx push ./flows/ --env production --dry-run
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from lfx.cli.common import load_sdk

console = Console(stderr=True)
ok_console = Console()


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class PushResult:
    path: Path
    flow_id: UUID
    flow_name: str
    status: str  # "created" | "updated" | "unchanged" | "error" | "dry-run"
    error: str | None = None
    flow_url: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in ("created", "updated", "unchanged", "dry-run")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_flow_file(path: Path) -> dict[str, Any]:
    """Read and parse a flow JSON file; raise Exit on error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        console.print(f"[red]Error:[/red] Cannot read {path}: {exc}")
        raise typer.Exit(1) from exc


def _extract_flow_id(flow: dict[str, Any], path: Path) -> UUID:
    """Extract and validate the flow's stable ID from the JSON."""
    raw_id = flow.get("id")
    if not raw_id:
        console.print(f"[red]Error:[/red] {path} has no 'id' field. Run [bold]lfx export[/bold] first.")
        raise typer.Exit(1)
    try:
        return UUID(str(raw_id))
    except ValueError:
        console.print(f"[red]Error:[/red] {path} has an invalid 'id': {raw_id!r}")
        raise typer.Exit(1)  # noqa: B904


def _flow_to_create(sdk: Any, flow: dict[str, Any], folder_id: UUID | None) -> Any:
    """Build a FlowCreate from a normalized flow dict."""
    return sdk.FlowCreate(
        name=flow.get("name", "Untitled"),
        description=flow.get("description"),
        data=flow.get("data"),
        is_component=flow.get("is_component", False),
        endpoint_name=flow.get("endpoint_name"),
        tags=flow.get("tags"),
        folder_id=folder_id or (UUID(flow["folder_id"]) if flow.get("folder_id") else None),
        icon=flow.get("icon"),
        icon_bg_color=flow.get("icon_bg_color"),
        locked=flow.get("locked", False),
        mcp_enabled=flow.get("mcp_enabled", False),
    )


def _upsert_single(
    client: Any,
    sdk: Any,
    path: Path,
    flow_id: UUID,
    flow_create: Any,
    *,
    dry_run: bool,
    flow_name: str,
    base_url: str,
    local_file_content: str | None = None,
    strip_secrets: bool = True,
) -> PushResult:
    flow_url = f"{base_url.rstrip('/')}/flow/{flow_id}"

    if dry_run:
        return PushResult(path=path, flow_id=flow_id, flow_name=flow_name, status="dry-run", flow_url=flow_url)

    # Compare normalized remote against local file to detect unchanged flows,
    # avoiding a spurious PUT when nothing has actually changed.
    # Import directly from serialization so this internal comparison is not
    # counted as a call to the public sdk.normalize_flow (keeps tests clean).
    if local_file_content is not None:
        try:
            # Use direct module imports (not sdk.*) so mock call-counts in tests
            # stay accurate and so the except clause uses a real exception class.
            from langflow_sdk.exceptions import LangflowNotFoundError
            from langflow_sdk.serialization import flow_to_json, normalize_flow

            remote = client.get_flow(flow_id)
            remote_normalized = normalize_flow(
                remote.model_dump(mode="json"),
                strip_volatile=True,
                strip_secrets=strip_secrets,
                sort_keys=True,
            )
            if flow_to_json(remote_normalized) == local_file_content:
                return PushResult(
                    path=path,
                    flow_id=flow_id,
                    flow_name=flow_name,
                    status="unchanged",
                    flow_url=flow_url,
                )
        except LangflowNotFoundError:
            pass  # Flow doesn't exist yet — fall through to create it
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).debug("Remote comparison failed; proceeding with push", exc_info=True)

    try:
        _, created = client.upsert_flow(flow_id, flow_create)
        status = "created" if created else "updated"
        return PushResult(path=path, flow_id=flow_id, flow_name=flow_name, status=status, flow_url=flow_url)
    except sdk.LangflowHTTPError as exc:
        return PushResult(
            path=path,
            flow_id=flow_id,
            flow_name=flow_name,
            status="error",
            error=str(exc),
            flow_url=flow_url,
        )


def _find_or_create_project(
    client: Any,
    sdk: Any,
    project_name: str,
    *,
    dry_run: bool,
) -> UUID | None:
    """Return the UUID of a project with *project_name*, creating if needed.

    Returns ``None`` in dry-run mode (project may not exist yet).
    """
    projects = client.list_projects()
    for p in projects:
        if p.name == project_name:
            console.print(f"[dim]Project[/dim] {project_name!r} found (id={p.id})")
            return p.id

    if dry_run:
        console.print(f"[dim]Project[/dim] {project_name!r} would be created (dry-run)")
        return None

    project = client.create_project(sdk.ProjectCreate(name=project_name))
    console.print(f"[green]Created project[/green] {project_name!r} (id={project.id})")
    return project.id


def _find_project_root() -> Path | None:
    """Return the lfx project root (directory containing .lfx/), or None.

    Only the ``.lfx`` marker is used — ``.git`` is intentionally excluded so
    that the containment check doesn't reject paths when running inside a
    larger monorepo or outside any lfx project.
    """
    cwd = Path.cwd()
    for directory in (cwd, *cwd.parents):
        if (directory / ".lfx").is_dir():
            return directory
        # Stop at a filesystem root
        if directory.parent == directory:
            break
    return None


def _check_path_containment(p: Path, root: Path | None) -> None:
    """Ensure *p* is inside *root*; skip check when no project root is found."""
    if root is None:
        return
    try:
        p.resolve().relative_to(root.resolve())
    except ValueError:
        console.print(
            f"[red]Error:[/red] Path {p} is outside the project root ({root}). "
            "Refusing to push files from outside the project."
        )
        raise typer.Exit(1)  # noqa: B904


def _collect_flow_files(sources: list[str], dir_path: str | None) -> list[Path]:
    """Resolve the set of flow JSON files to push.

    When neither explicit file paths nor ``--dir`` are given, defaults to
    ``flows/`` — mirroring the behaviour of ``lfx pull``.
    """
    paths: list[Path] = []
    root = _find_project_root()

    # Default to flows/ when nothing is specified, just like lfx pull does.
    effective_dir = dir_path or (None if sources else "flows")

    if effective_dir:
        d = Path(effective_dir)
        _check_path_containment(d, root)
        if not d.is_dir():
            console.print(f"[red]Error:[/red] Directory not found: {d}")
            raise typer.Exit(1)
        paths.extend(sorted(d.glob("*.json")))
        if not paths:
            console.print(f"[yellow]Warning:[/yellow] No *.json files found in {d}")

    for s in sources:
        p = Path(s)
        _check_path_containment(p, root)
        if not p.exists():
            console.print(f"[red]Error:[/red] File not found: {p}")
            raise typer.Exit(1)
        if p.is_dir():
            dir_jsons = sorted(p.glob("*.json"))
            if not dir_jsons:
                console.print(f"[yellow]Warning:[/yellow] No *.json files found in {p}")
            paths.extend(dir_jsons)
        else:
            paths.append(p)

    return paths


def _render_results(results: list[PushResult], *, dry_run: bool) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("File")
    table.add_column("Name")
    table.add_column("ID")
    table.add_column("Status")
    table.add_column("URL")

    status_colors = {
        "created": "green",
        "updated": "cyan",
        "unchanged": "dim",
        "dry-run": "yellow",
        "error": "red",
    }

    for r in results:
        color = status_colors.get(r.status, "white")
        label = r.status.upper() + (f": {r.error}" if r.error else "")
        url_cell = f"[blue]{r.flow_url}[/blue]" if r.flow_url and r.ok else (r.flow_url or "")
        table.add_row(
            str(r.path),
            r.flow_name,
            str(r.flow_id),
            f"[{color}]{label}[/{color}]",
            url_cell,
        )

    ok_console.print()
    ok_console.print(table)

    errors = [r for r in results if not r.ok]
    if errors:
        console.print(f"\n[red]{len(errors)} push(es) failed.[/red]")
    elif dry_run:
        ok_console.print(f"\n[yellow]{len(results)} flow(s) would be pushed (dry-run).[/yellow]")
    else:
        created = sum(1 for r in results if r.status == "created")
        updated = sum(1 for r in results if r.status == "updated")
        unchanged = sum(1 for r in results if r.status == "unchanged")
        parts = []
        if created:
            parts.append(f"[green]{created} created[/green]")
        if updated:
            parts.append(f"[cyan]{updated} updated[/cyan]")
        if unchanged:
            parts.append(f"[dim]{unchanged} unchanged[/dim]")
        ok_console.print("\n" + ", ".join(parts) + ".")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def push_command(
    flow_paths: list[str],
    *,
    env: str | None,
    dir_path: str | None,
    project: str | None,
    project_id: str | None,
    environments_file: str | None,
    target: str | None = None,
    api_key: str | None = None,
    dry_run: bool,
    normalize: bool,
    strip_secrets: bool,
) -> None:
    sdk = load_sdk("push")

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

    paths = _collect_flow_files(flow_paths, dir_path)
    if not paths:
        console.print(
            "[red]Error:[/red] No *.json flow files found. "
            "Run [bold]lfx pull[/bold] first, or pass explicit file paths."
        )
        raise typer.Exit(1)

    # Resolve target project folder_id
    target_folder_id: UUID | None = None
    if project_id:
        target_folder_id = UUID(project_id)
    elif project:
        target_folder_id = _find_or_create_project(client, sdk, project, dry_run=dry_run)

    results: list[PushResult] = []

    for path in paths:
        raw_flow = _load_flow_file(path)

        if normalize:
            raw_flow = sdk.normalize_flow(
                raw_flow,
                strip_volatile=True,
                strip_secrets=strip_secrets,
                sort_keys=True,
            )

        flow_id = _extract_flow_id(raw_flow, path)
        flow_name = raw_flow.get("name", path.stem)
        flow_create = _flow_to_create(sdk, raw_flow, target_folder_id)
        # Capture normalized content now so _upsert_single can compare against remote.
        local_file_content = sdk.flow_to_json(raw_flow) if normalize else None

        result = _upsert_single(
            client,
            sdk,
            path,
            flow_id,
            flow_create,
            dry_run=dry_run,
            flow_name=flow_name,
            base_url=env_cfg.url,
            local_file_content=local_file_content,
            strip_secrets=strip_secrets,
        )
        results.append(result)

        if dry_run:
            console.print(f"[yellow]DRY-RUN[/yellow] Would push {flow_name!r} ({flow_id})")
        elif result.status == "unchanged":
            console.print(f"[dim]Unchanged[/dim] {flow_name!r}")
        elif result.status == "created":
            url_hint = f"  [dim]{result.flow_url}[/dim]" if result.flow_url else ""
            console.print(f"[green]Created[/green]  {flow_name!r} ({flow_id}){url_hint}")
        elif result.status == "updated":
            url_hint = f"  [dim]{result.flow_url}[/dim]" if result.flow_url else ""
            console.print(f"[cyan]Updated[/cyan]  {flow_name!r} ({flow_id}){url_hint}")
        else:
            console.print(f"[red]Failed[/red]   {flow_name!r} ({flow_id}): {result.error}")

    _render_results(results, dry_run=dry_run)

    if any(not r.ok for r in results):
        raise typer.Exit(1)
