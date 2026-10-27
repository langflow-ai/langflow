"""The process ``langflow upgrade-check`` runs the check in: read the options, check, write the report.

The command starts this module with every ``LANGFLOW_`` variable removed from its environment and
``LANGFLOW_CONFIG_DIR`` pointing at a throwaway folder, and sends the options as JSON on stdin.
Component code can build Langflow's settings (MCP components do when they are created), which
saves a secret key. Isolated like this, nothing reads the server's environment and nothing lands
in its folders.

Exit codes: 0 when nothing needs action, 1 when a flow fails or the source has a blocker, 2 when
the check could not finish.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from collections import Counter
from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, get_args

from lfx.extension import SLOT_EXTRA, SLOT_OFFICIAL
from lfx.interface.components import _read_component_index
from lfx.upgrade.checker import NodeStatusLiteral
from lfx.upgrade.registry import UpgradeRegistryError, load_upgrade_registry

from langflow.upgrade_check.engine import Target, TargetSettings, check_source, flow_status
from langflow.upgrade_check.reader import SourceDatabaseError, open_source
from langflow.utils.version import get_version_info

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from langflow.upgrade_check.engine import FlowResult

FORMAT_VERSION = 1
# Reasons printed per node without --json; the report has them all.
_REASONS_SHOWN = 3


class CheckError(Exception):
    """The check cannot finish. The message says what to change."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def main() -> int:
    options = json.load(sys.stdin)
    as_json = options["json"]
    # The events and the summary own stdout. Anything else written there, such as a custom component
    # that prints when it loads, goes to stderr, so every stdout line with --json is an event.
    out = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8")
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    on_flow = (lambda result: _emit(out, "flow", flow=result.to_dict())) if as_json else None
    try:
        report, listed = run(options, on_flow)
        if options["output"]:
            Path(options["output"]).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except CheckError as exc:
        _fail(out, exc.code, str(exc), as_json=as_json)
        return 2
    except Exception as exc:  # noqa: BLE001 - a crash still ends with one line that says so
        traceback.print_exc()
        message = f"the check stopped: {_first_line(exc)}. The traceback is on stderr."
        _fail(out, "check_failed", message, as_json=as_json)
        return 2
    if as_json:
        _emit(out, "report", report=report)
    else:
        _print_summary(out, report, listed, options["output"])
    return 1 if _needs_action(report) else 0


def run(options: Mapping[str, Any], on_flow: Callable[[FlowResult], None] | None = None) -> tuple[dict, list]:
    """Check the source the options name and return the report, with the results of the flows it lists."""
    settings = TargetSettings(
        **{**options["settings"], "components_path": tuple(options["settings"]["components_path"])}
    )
    if missing := [path for path in settings.components_path if not Path(path).is_dir()]:
        msg = f"no folder at {', '.join(missing)}. Pass --components-path with the folders the upgraded server loads."
        raise CheckError(msg, code="components_path_missing")
    with ExitStack() as stack:
        try:
            source = stack.enter_context(open_source(options["database_url"]))
        except Exception as exc:
            raise CheckError(_source_message(exc), code="source_unreadable") from exc
        policy = source.catalog_policy()
        try:
            all_types = load_upgrade_registry(components_path=settings.loaded_components_path)
        except UpgradeRegistryError as exc:
            msg = f"cannot load this release's components: {exc} ({_first_line(exc.__cause__ or exc)})"
            raise CheckError(msg, code="registry_unavailable") from exc

        flows = dict.fromkeys(("ok", "warn", "fail"), 0)
        nodes = dict.fromkeys(get_args(NodeStatusLiteral), 0)
        kinds: Counter[str] = Counter()
        listed: list[FlowResult] = []
        errors: list[dict[str, Any]] = []
        for result in check_source(source, Target.from_registry(all_types, settings, policy.snapshot)):
            if on_flow:
                on_flow(result)
            kinds[result.kind] += 1
            flows[result.status] += 1
            nodes["ok"] += result.ok_nodes
            for node in result.nodes:
                nodes[node.status] += 1
            # An ok flow with an outdated_safe node is listed too, so the update step finds every node.
            if result.nodes or result.error:
                listed.append(result)
            if result.error:
                errors.append({"kind": result.kind, "id": result.id, "status": "warn", "message": result.error})
        if policy.data_error:
            message = (
                f"the catalog rules could not be read ({policy.data_error}), and the upgraded server would not "
                "start on them. Fix the active policy bundle before upgrading."
            )
            errors.append({"kind": "catalog_rules", "id": None, "status": "fail", "message": message})

        report = {
            "format_version": FORMAT_VERSION,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": {
                "dialect": source.dialect,
                "alembic_revision": ", ".join(source.alembic_revisions) or None,
                "counts": {
                    "flows": kinds["flow"],
                    "components": kinds["component"],
                    "flow_versions": kinds["flow_version"],
                },
            },
            "target": _target(all_types, settings),
            "settings": {
                **asdict(settings),
                "catalog_rules": {
                    # Sources before 1.12 have no rule tables.
                    "from": "policy_bundle_active" if source.has_policy_bundle else None,
                    "blocked_component_keys": sorted(policy.snapshot.blocked_component_keys),
                    "blocked_template_keys": sorted(policy.snapshot.blocked_template_keys),
                },
            },
            "summary": {"flows": flows, "nodes": nodes},
            "flows": [result.to_dict() for result in listed],
            "errors": errors,
        }
    return report, listed


def _target(all_types: Mapping[str, Any], settings: TargetSettings) -> dict[str, Any]:
    """This release as the check loaded it: versions, the component index, bundles, and custom components."""
    # A discovered component's address ends with its slot: installed bundles are official, folders
    # from the components path are extra.
    entries = [entry for components in all_types.values() for entry in components.values()]
    slots = [(entry, (entry.get("namespaced_id") or "").rpartition("@")[2]) for entry in entries]
    bundles = {
        f"{entry['extension']}=={entry.get('extension_version')}"
        for entry, slot in slots
        if slot.startswith(SLOT_OFFICIAL) and entry.get("extension")
    }
    try:
        lfx_version = version("lfx")
    except PackageNotFoundError:
        lfx_version = None
    return {
        "langflow": get_version_info()["version"],
        "lfx": lfx_version,
        "component_index_sha256": (_read_component_index(None) or {}).get("sha256"),
        "bundles": sorted(bundles),
        "custom_components": {
            "path": settings.loaded_components_path,
            "count": sum(slot.startswith(SLOT_EXTRA) for _, slot in slots),
        },
    }


def _needs_action(report: Mapping[str, Any]) -> bool:
    return bool(report["summary"]["flows"]["fail"]) or any(error["status"] == "fail" for error in report["errors"])


def _source_message(exc: Exception) -> str:
    if isinstance(exc, SourceDatabaseError):
        return str(exc)
    if isinstance(exc, ModuleNotFoundError):
        return (
            f"cannot read the source database: {exc}. Install the PostgreSQL driver next to this Langflow, "
            "for example pip install 'langflow[postgresql]'."
        )
    return (
        f"cannot read the source database: {_first_line(exc)}. Check --database-url, for example "
        "sqlite:////absolute/path/langflow.db or "
        "postgresql://user:password@host:5432/langflow."  # pragma: allowlist secret
    )


def _print_summary(out: IO[str], report: Mapping[str, Any], listed: list[FlowResult], output: str | None) -> None:
    flows = report["summary"]["flows"]
    out.write(
        f"Checked the flows, saved components and running flow versions: "
        f"{flows['ok']} ok, {flows['warn']} warn, {flows['fail']} fail.\n"
    )
    for result in sorted(listed, key=lambda result: result.status != "fail"):
        if result.status == "ok":
            continue
        owner = (result.owner or {}).get("username")
        out.write(f"\n{result.status:4}  {result.kind} {result.name!r} ({result.id}), owner {owner}\n")
        if result.error:
            out.write(f"      {result.error}\n")
        # The nodes that make the flow fail or warn.
        for node in (node for node in result.nodes if flow_status([node]) == result.status):
            out.write(f"      {node.display_name} ({node.id}): {node.status}, runs {node.runs}\n")
            for reason in node.reasons[:_REASONS_SHOWN]:
                field = f" {reason['field']}" if reason["field"] else ""
                out.write(f"        - {reason['code']}{field}: {reason['message']}\n")
            if len(node.reasons) > _REASONS_SHOWN:
                out.write(f"        - and {len(node.reasons) - _REASONS_SHOWN} more in the report\n")
    for error in report["errors"]:
        if error["status"] == "fail":
            out.write(f"\nfail  {error['message']}\n")
    out.write(
        "\nFix what is marked fail before the upgrade.\n"
        if _needs_action(report)
        else "\nNothing blocks the upgrade.\n"
    )
    if output:
        out.write(f"Report written to {output}.\n")
    out.flush()


def _emit(out: IO[str], event: str, **fields: Any) -> None:
    out.write(json.dumps({"event": event, **fields}, default=str) + "\n")
    out.flush()


def _fail(out: IO[str], code: str, message: str, *, as_json: bool) -> None:
    if as_json:
        _emit(out, "error", code=code, message=message)
    else:
        sys.stderr.write(f"The upgrade check could not finish: {message}\n")


def _first_line(exc: BaseException) -> str:
    lines = str(exc).strip().splitlines()
    return f"{type(exc).__name__}: {lines[0] if lines else ''}"


if __name__ == "__main__":
    sys.exit(main())
