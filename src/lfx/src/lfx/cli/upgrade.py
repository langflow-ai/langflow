"""Implementation of `lfx upgrade <flow.json>`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from lfx.upgrade.applier import apply_safe_upgrades
from lfx.upgrade.checker import CompatibilityReport, build_registry_lookup, check_flow_compatibility
from lfx.utils.flow_envelope import merge_flow_envelope, split_flow_envelope

# ASCII status markers (no Unicode glyphs) so output is safe on Windows cp1252 consoles,
# where non-ASCII symbols would raise UnicodeEncodeError or render as mojibake.
_STATUS_MARKERS = {
    "ok": "[OK]",
    "outdated_safe": "[SAFE]",
    "outdated_breaking": "[BREAKING]",
    "blocked": "[BLOCKED]",
}


def load_registry_from_index() -> dict[str, Any]:
    """Load the bundled component index and return a flat all_types_dict.

    Raises:
        typer.Exit: if the bundled registry is empty or missing. Running the checker against
            an empty registry would silently classify *every* node as ``blocked``: a
            tooling-level failure masquerading as a flow-level problem. Fail loudly instead.
    """
    from lfx.interface.components import _read_component_index

    blob = _read_component_index(None)
    if not blob or "entries" not in blob:
        typer.echo(
            "Error: the bundled component registry is empty or missing, so compatibility "
            "cannot be checked. Try reinstalling lfx (e.g. `pip install --force-reinstall lfx`).",
            err=True,
        )
        raise typer.Exit(1)
    all_types: dict[str, Any] = {}
    for category, components in blob["entries"]:
        all_types.setdefault(category, {}).update(components)
    return all_types


def _print_report(report: CompatibilityReport) -> None:
    if report.is_clean:
        typer.echo("All components are up to date.")
        return

    for n in report.nodes:
        marker = _STATUS_MARKERS.get(n.status, "[?]")
        typer.echo(f"  {marker} {n.display_name} ({n.component_type}) - id: {n.node_id}")


def upgrade_command(
    flow_path: Path,
    *,
    write: bool,
    strict: bool = False,
    registry: dict[str, Any] | None = None,
) -> None:
    if not flow_path.exists():
        typer.echo(f"Error: flow file does not exist: {flow_path}", err=True)
        raise typer.Exit(1)

    try:
        flow_data = json.loads(flow_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        typer.echo(f"Error reading flow: {e}", err=True)
        raise typer.Exit(1) from e

    # Exported Langflow flows may have an outer envelope:
    # {"name": ..., "data": {"nodes": [...], "edges": [...]}}
    # Split it off so the checker sees the inner graph; the envelope is re-attached on write.
    try:
        outer_envelope, inner_data = split_flow_envelope(flow_data)
    except TypeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e

    all_types = registry if registry is not None else load_registry_from_index()
    # Build the registry lookup once and reuse it for both the check and the apply step.
    registry_lookup = build_registry_lookup(all_types)
    report = check_flow_compatibility(inner_data, all_types, registry=registry_lookup)

    _print_report(report)

    wrote_safe = False
    if write and report.has_safe_updates:
        updated_inner, count = apply_safe_upgrades(
            inner_data, all_types, report, return_count=True, registry=registry_lookup
        )
        # Preserve the on-disk shape: keep the envelope (with metadata) when present, else stay flat.
        output = merge_flow_envelope(outer_envelope, updated_inner, wrap_bare=False)
        flow_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        typer.echo(f"Wrote {count} safe upgrade(s) to {flow_path}")
        wrote_safe = True

    if report.has_blocked or report.has_breaking:
        raise typer.Exit(1)

    # --strict: any component left not up to date is drift. Safe upgrades that were just
    # written no longer count; pending (unwritten) safe upgrades do.
    if strict and report.has_safe_updates and not wrote_safe:
        typer.echo(
            "Error: --strict: flow has pending safe upgrades. Re-run with --write to apply them.",
            err=True,
        )
        raise typer.Exit(1)
