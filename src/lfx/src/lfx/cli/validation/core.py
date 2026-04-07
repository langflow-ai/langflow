"""Core validation types, constants, and orchestrator for flow validation.

Contains the ValidationIssue and ValidationResult dataclasses, level constants,
the main validate_flow_file orchestrator, and CLI rendering / path helpers.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from lfx.cli.validation.semantic import (
    _check_component_existence,
    _check_edge_type_compatibility,
    _check_missing_credentials,
    _check_required_inputs,
)
from lfx.cli.validation.structural import (
    _check_orphaned_nodes,
    _check_structural,
    _check_unused_nodes,
    _check_version_mismatch,
)

console = Console(stderr=True)
ok_console = Console()

# Validation level constants
LEVEL_STRUCTURAL = 1
LEVEL_COMPONENTS = 2
LEVEL_EDGE_TYPES = 3
LEVEL_REQUIRED_INPUTS = 4

# Keep underscore-prefixed aliases for backwards compatibility
_LEVEL_STRUCTURAL = LEVEL_STRUCTURAL
_LEVEL_COMPONENTS = LEVEL_COMPONENTS
_LEVEL_EDGE_TYPES = LEVEL_EDGE_TYPES
_LEVEL_REQUIRED_INPUTS = LEVEL_REQUIRED_INPUTS


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    level: int
    severity: str  # "error" | "warning"
    node_id: str | None
    node_name: str | None
    message: str


@dataclass
class ValidationResult:
    path: Path
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node_display_name(node: dict[str, Any]) -> str | None:
    return node.get("data", {}).get("node", {}).get("display_name") or node.get("data", {}).get("id") or node.get("id")


def _get_lf_version() -> str | None:
    """Return the installed Langflow version string, or *None* if not installed.

    Tries the four known package names in order of preference so the check
    works with released builds, nightly builds, and editable installs.
    """
    from importlib.metadata import PackageNotFoundError, version

    for pkg in ("langflow-base", "langflow", "langflow-base-nightly", "langflow-nightly"):
        try:
            return version(pkg)
        except PackageNotFoundError:
            continue
    return None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def validate_flow_file(
    path: Path,
    *,
    level: int = LEVEL_REQUIRED_INPUTS,
    skip_components: bool = False,
    skip_edge_types: bool = False,
    skip_required_inputs: bool = False,
    skip_version_check: bool = False,
    skip_credentials: bool = False,
) -> ValidationResult:
    result = ValidationResult(path=path)

    try:
        raw = path.read_text(encoding="utf-8")
        flow: dict[str, Any] = json.loads(raw)
    except OSError as exc:
        result.issues.append(
            ValidationIssue(
                level=LEVEL_STRUCTURAL,
                severity="error",
                node_id=None,
                node_name=None,
                message=f"Cannot read file: {exc}",
            )
        )
        return result
    except json.JSONDecodeError as exc:
        result.issues.append(
            ValidationIssue(
                level=LEVEL_STRUCTURAL,
                severity="error",
                node_id=None,
                node_name=None,
                message=f"Invalid JSON: {exc}",
            )
        )
        return result

    # Level 1 - structural (JSON shape + orphaned/unused node checks)
    can_continue = _check_structural(flow, result)
    if can_continue:
        _check_orphaned_nodes(flow, result)
        _check_unused_nodes(flow, result)
        # Extended: version mismatch / outdated components
        if not skip_version_check:
            _check_version_mismatch(flow, result)
    if not can_continue or level < LEVEL_COMPONENTS:
        return result

    # Level 2 - component existence
    if not skip_components:
        _check_component_existence(flow, result)
    if level < LEVEL_EDGE_TYPES:
        return result

    # Level 3 - edge type compatibility
    if not skip_edge_types:
        _check_edge_type_compatibility(flow, result)
    if level < LEVEL_REQUIRED_INPUTS:
        return result

    # Level 4 - required inputs + extended: missing credentials
    if not skip_required_inputs:
        _check_required_inputs(flow, result)
    if not skip_credentials:
        _check_missing_credentials(flow, result)

    return result


# ---------------------------------------------------------------------------
# CLI rendering and path helpers
# ---------------------------------------------------------------------------


def _render_result(
    result: ValidationResult,
    *,
    index: int,
    total: int,
    verbose: bool,
    strict: bool = False,
) -> None:
    counter = f"[dim][{index}/{total}][/dim] " if total > 1 else ""
    label = f"[bold]{result.path}[/bold]"
    passes = result.ok and not (strict and result.warnings)
    if passes:
        ok_console.print(f"{counter}[green]\u2713[/green] {label}")
    else:
        console.print(f"{counter}[red]\u2717[/red] {label}")

    show_issues = verbose or not passes
    if show_issues:
        for issue in result.issues:
            effective_severity = "error" if (strict and issue.severity == "warning") else issue.severity
            color = "red" if effective_severity == "error" else "yellow"
            loc = f" [{issue.node_name or issue.node_id}]" if (issue.node_id or issue.node_name) else ""
            console.print(f"  [{color}][L{issue.level} {effective_severity.upper()}][/{color}]{loc} {issue.message}")


def _expand_paths(raw_paths: list[str]) -> list[Path]:
    """Expand each entry to a list of .json files.

    * If the path is a directory, collect every ``*.json`` file recursively.
    * If the path is a file, return it as-is.
    * If the path does not exist, print an error and exit 2.
    """
    paths: list[Path] = []
    for raw in raw_paths:
        p = Path(raw)
        if not p.exists():
            console.print(f"[red]Error:[/red] Path not found: {p}")
            raise typer.Exit(2)
        if p.is_dir():
            found = sorted(p.rglob("*.json"))
            if not found:
                console.print(f"[yellow]Warning:[/yellow] No .json files found in {p}")
            paths.extend(found)
        else:
            paths.append(p)
    return paths


_DEFAULT_FLOWS_DIR = "flows"


def validate_command(
    flow_paths: list[str],
    level: int,
    *,
    skip_components: bool,
    skip_edge_types: bool,
    skip_required_inputs: bool,
    skip_version_check: bool,
    skip_credentials: bool,
    strict: bool,
    verbose: bool,
    output_format: str,
) -> None:
    if not flow_paths:
        flow_paths = [_DEFAULT_FLOWS_DIR]

    paths = _expand_paths(flow_paths)

    if not paths:
        console.print("[yellow]No flow files to validate.[/yellow]")
        raise typer.Exit(0)

    results: list[ValidationResult] = []
    for i, p in enumerate(paths, start=1):
        result = validate_flow_file(
            p,
            level=level,
            skip_components=skip_components,
            skip_edge_types=skip_edge_types,
            skip_required_inputs=skip_required_inputs,
            skip_version_check=skip_version_check,
            skip_credentials=skip_credentials,
        )
        results.append(result)
        if output_format != "json":
            _render_result(result, index=i, total=len(paths), verbose=verbose, strict=strict)

    if output_format == "json":
        import json as _json

        out = [
            {
                "path": str(r.path),
                "ok": r.ok if not strict else (not r.errors and not r.warnings),
                "issues": [
                    {
                        "level": i.level,
                        "severity": i.severity,
                        "node_id": i.node_id,
                        "node_name": i.node_name,
                        "message": i.message,
                    }
                    for i in r.issues
                ],
            }
            for r in results
        ]
        sys.stdout.write(_json.dumps(out, indent=2) + "\n")
    elif len(paths) > 1:
        passed = sum(1 for r in results if r.ok and not (strict and r.warnings))
        failed = len(results) - passed
        color = "green" if failed == 0 else "red"
        ok_console.print(f"\n[{color}]Validated {len(paths)} flows: {passed} passed, {failed} failed.[/{color}]")

    if any((not r.ok) or (strict and r.warnings) for r in results):
        raise typer.Exit(1)
