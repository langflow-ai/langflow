"""Implementation of `lfx upgrade <flow.json>`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from lfx.upgrade.applier import apply_safe_upgrades
from lfx.upgrade.checker import CompatibilityReport, check_flow_compatibility


def load_registry_from_index() -> dict[str, Any]:
    """Load the bundled component index and return a flat all_types_dict."""
    from lfx.interface.components import _read_component_index

    blob = _read_component_index(None)
    if not blob or "entries" not in blob:
        return {}
    all_types: dict[str, Any] = {}
    for category, components in blob["entries"]:
        all_types.setdefault(category, {}).update(components)
    return all_types


def _print_report(report: CompatibilityReport) -> None:
    if report.is_clean:
        typer.echo("✓ All components are up to date.")
        return

    for n in report.nodes:
        icon = {"ok": "✓", "outdated_safe": "~", "outdated_breaking": "✗", "blocked": "✗"}.get(n.status, "?")
        typer.echo(f"  {icon} [{n.status}] {n.display_name} ({n.component_type}) — id: {n.node_id}")


def upgrade_command(
    flow_path: Path,
    *,
    write: bool,
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
    # Keep a reference to the outer envelope so we can reconstruct it on write.
    has_envelope = "data" in flow_data and "nodes" in flow_data.get("data", {})
    inner_data = flow_data["data"] if has_envelope else flow_data

    all_types = load_registry_from_index()
    report = check_flow_compatibility(inner_data, all_types)

    _print_report(report)

    if write and report.has_safe_updates:
        updated_inner, count = apply_safe_upgrades(inner_data, all_types, report, return_count=True)
        output = {**flow_data, "data": updated_inner} if has_envelope else updated_inner
        flow_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        typer.echo(f"✓ Wrote {count} safe upgrade(s) to {flow_path}")

    if report.has_blocked or report.has_breaking:
        raise typer.Exit(1)
