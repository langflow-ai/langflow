#!/usr/bin/env python3
"""CI gate: detect component changes in ``component_index.json`` that break saved flows.

"Breaking" is defined by the repo's own upgrade checker,
``lfx.upgrade.checker.has_breaking_change``, which the restricted-mode build path also uses.
The gate compares each component's index entry before and after the PR as if the old entry
were a saved node and the new entry the registry. It adds one check the upgrade checker
doesn't make: removing an input that accepts connections (non-empty ``input_types``), because
the editor's Update action rebuilds the node from the new template and drops edges into it.

The comparison is three-way. A change is blamed on the PR only when it breaks against both the
base-branch tip and the PR's merge base, so changes that landed on the base branch after the
PR branched are not reported.

A component missing from the PR head is diagnosed before it is reported:

- its source file still defines the class, so index regeneration dropped it (for example, an
  optional dependency was missing when the index was built);
- it moved to a provider bundle under ``src/bundles``, or it is renamed through
  ``LEGACY_TYPE_ALIASES``, so saved flows still resolve;
- otherwise it was removed.

Stdlib-only by design so it runs on a bare runner without ``uv sync``. The checker module and
type migrations are loaded from files the workflow extracts from the base branch, so a PR
cannot weaken the rule it is judged by. Aliases and bundle sources are read from the PR head,
because adding an alias or moving a component legitimately changes whether saved flows
resolve; an alias must point at a component that exists.
"""

from __future__ import annotations

import argparse
import ast
import copy
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from types import ModuleType

ComponentIndex = dict[str, dict[str, Any]]

ALIASES_FILE = Path("src/lfx/src/lfx/utils/component_aliases.py")
BUNDLES_DIR = Path("src/bundles")
EXTERNAL_ALIAS = re.compile(r"^ext:[^:]+:([A-Za-z_][A-Za-z0-9_]*)@")

# Field types the editor renders as plain widgets rather than connection handles. Mirrors
# LANGFLOW_SUPPORTED_TYPES in src/frontend/src/constants/constants.ts; keep the two in sync.
FRONTEND_WIDGET_TYPES = frozenset(
    {
        "str", "bool", "float", "code", "prompt", "mustache", "file", "int", "dict", "NestedDict", "table",
        "link", "slider", "tab", "sortableList", "actionPicker", "duration", "connect", "auth", "query", "mcp",
        "tools", "data_display",
    }
)  # fmt: skip


@dataclass(frozen=True)
class Problem:
    level: Literal["error", "notice"]
    message: str


class IndexReadError(Exception):
    """An index or helper file could not be read or has an unexpected shape."""


class CheckerTooOldError(IndexReadError):
    """The base branch's upgrade checker predates ``has_breaking_change``."""


def load_index(path: Path) -> tuple[ComponentIndex, list[str]]:
    """Map each component key (the saved node's ``data.type``) to its index entry.

    Returns the index and a warning per duplicate key. The index builder keys components per
    category, so the same key can appear in two categories; the first entry is kept.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        index: ComponentIndex = {}
        warnings: list[str] = []
        for _category, components in data["entries"]:
            for key, entry in components.items():
                if key in index:
                    warnings.append(
                        f"{path.name}: component {key!r} appears in more than one category; using the first."
                    )
                    continue
                index[key] = entry
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        msg = f"Could not read component index {path}: {type(exc).__name__}: {exc}"
        raise IndexReadError(msg) from exc
    return index, warnings


def load_checker(path: Path) -> ModuleType:
    """Load ``lfx/upgrade/checker.py`` from a file path; its top-level imports are stdlib only."""
    spec = importlib.util.spec_from_file_location("component_compat_upgrade_checker", path)
    if spec is None or spec.loader is None:
        msg = f"Could not load upgrade checker from {path}"
        raise IndexReadError(msg)
    module = importlib.util.module_from_spec(spec)
    # Dataclasses resolve string annotations through sys.modules, so register before executing.
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except (OSError, SyntaxError, ImportError) as exc:
        msg = f"Could not load upgrade checker from {path}: {type(exc).__name__}: {exc}"
        raise IndexReadError(msg) from exc
    if not hasattr(module, "has_breaking_change"):
        msg = f"{path} predates has_breaking_change, so the gate can't run against this base branch."
        raise CheckerTooOldError(msg)
    return module


def load_literal_dict(path: Path, name: str) -> dict[str, str]:
    """Read a module-level ``name = {...}`` dict literal from a Python file without importing it."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        msg = f"Could not parse {path}: {type(exc).__name__}: {exc}"
        raise IndexReadError(msg) from exc
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        else:
            continue
        if isinstance(target, ast.Name) and target.id == name and value is not None:
            return ast.literal_eval(value)
    msg = f"{path} does not define {name}"
    raise IndexReadError(msg)


def migrate_types(entry: dict[str, Any], migrations: dict[str, str]) -> dict[str, Any]:
    """Return a copy of ``entry`` with legacy type names mapped, as edge validation does."""
    migrated = copy.deepcopy(entry)
    for output in migrated.get("outputs") or []:
        output["types"] = [migrations.get(t, t) for t in output.get("types") or []]
    for field in (migrated.get("template") or {}).values():
        if isinstance(field, dict) and field.get("input_types"):
            field["input_types"] = [migrations.get(t, t) for t in field["input_types"]]
    return migrated


def without_added_outputs(new: dict[str, Any], old: dict[str, Any]) -> dict[str, Any]:
    """Return ``new`` without outputs that ``old`` lacks.

    ``has_breaking_change`` requires the output name sets to be equal, so it reports a newly
    added output as breaking. A saved flow has no edges from an output it never had, so the
    gate only lets removed or changed outputs count.
    """
    old_names = {output.get("name") for output in old.get("outputs") or []}
    trimmed = dict(new)
    trimmed["outputs"] = [output for output in new.get("outputs") or [] if output.get("name") in old_names]
    return trimmed


def breaks_saved_node(checker: ModuleType, new: dict[str, Any], old: dict[str, Any]) -> bool:
    """Return True if a saved node shaped like ``old`` breaks against ``new``."""
    trimmed = without_added_outputs(new, old)
    if old.get("outputs") and new.get("outputs") and not trimmed["outputs"]:
        # Every saved output was replaced. Trimming left no outputs, and has_breaking_change
        # skips the comparison when the registry declares none, so catch it here. A component
        # that declares no outputs at all builds them dynamically (Run Flow), which the
        # checker deliberately doesn't compare.
        return True
    if checker.has_breaking_change(trimmed, old):
        return True
    return _loses_tool_mode(checker, new, old)


def _supports_tool_mode(entry: dict[str, Any]) -> bool:
    return any(isinstance(field, dict) and field.get("tool_mode") for field in (entry.get("template") or {}).values())


def _loses_tool_mode(checker: ModuleType, new: dict[str, Any], old: dict[str, Any]) -> bool:
    """Return True if nodes saved in tool mode break because the component dropped tool mode.

    An index entry is never itself in tool mode, so check a tool-mode projection of it. Older
    checkers have no tool-mode branch and would misread the projection, so skip them.
    """
    if not hasattr(checker, "TOOL_OUTPUT_NAME") or not _supports_tool_mode(old):
        return False
    tool_node = {**old, "outputs": [{"name": checker.TOOL_OUTPUT_NAME, "types": ["Tool"]}]}
    return checker.has_breaking_change(new, tool_node)


def handle_fields(entry: dict[str, Any], transient: frozenset[str] = frozenset()) -> set[str]:
    """Return the fields the editor draws a connection handle for.

    Mirrors ``computeDisplayHandle`` in
    src/frontend/src/CustomNodes/GenericNode/components/RenderInputParameters/utils.ts
    (outside tool mode): model fields always get a handle; other fields get one when they accept
    ``input_types`` or aren't a plain widget type, unless they have a refresh button.
    """
    fields = set()
    for key, field in (entry.get("template") or {}).items():
        if key.startswith("_") or key in transient or not isinstance(field, dict):
            continue
        field_type = field.get("type")
        if field_type == "model" or (
            (field_type not in FRONTEND_WIDGET_TYPES or field.get("input_types")) and not field.get("refresh_button")
        ):
            fields.add(key)
    return fields


def _describe_change(old: dict[str, Any], new: dict[str, Any]) -> str:
    """Summarize the differences a reviewer should look at; the checker decides breakage."""
    details: list[str] = []
    old_outputs = {o.get("name"): o for o in old.get("outputs") or []}
    new_outputs = {o.get("name"): o for o in new.get("outputs") or []}
    if removed := sorted(set(old_outputs) - set(new_outputs), key=str):
        details.append(f"outputs removed: {', '.join(map(str, removed))}")
    for name in sorted(set(old_outputs) & set(new_outputs), key=str):
        before, after = old_outputs[name], new_outputs[name]
        if lost := sorted(set(before.get("types") or []) - set(after.get("types") or [])):
            details.append(f"output {name!r} no longer emits {', '.join(lost)}")
        if before.get("method") != after.get("method"):
            details.append(f"output {name!r} method changed")
        if before.get("allows_loop") != after.get("allows_loop"):
            details.append(f"output {name!r} allows_loop changed")
    old_template, new_template = old.get("template") or {}, new.get("template") or {}
    for key in sorted(set(new_template) - set(old_template)):
        field = new_template[key]
        if isinstance(field, dict) and field.get("required") and field.get("value") in (None, ""):
            details.append(f"new required input {key!r} has no default")
    for key in sorted(set(old_template) & set(new_template)):
        before, after = old_template[key], new_template[key]
        if not (isinstance(before, dict) and isinstance(after, dict) and after.get("input_types")):
            continue
        if lost := sorted(set(before.get("input_types") or []) - set(after["input_types"])):
            details.append(f"input {key!r} no longer accepts {', '.join(lost)}")
    if _supports_tool_mode(old) and not _supports_tool_mode(new):
        details.append("no longer supports tool mode")
    return "; ".join(details) or "see lfx.upgrade.checker.has_breaking_change"


def _source_defines_class(repo_root: Path, module_path: str) -> bool:
    """Return True if the module named in the entry's metadata still defines its class."""
    module, _, class_name = module_path.rpartition(".")
    if not module or not class_name:
        return False
    source = repo_root / "src" / "lfx" / "src" / Path(*module.split(".")).with_suffix(".py")
    try:
        text = source.read_text(encoding="utf-8")
    except OSError:
        return False
    return re.search(rf"^class {re.escape(class_name)}\b", text, re.MULTILINE) is not None


def _bundle_defining(repo_root: Path, key: str, class_name: str) -> str | None:
    """Return the bundle directory that defines the component, if any."""
    # ponytail: the `name =` pattern also matches input and output names in bundle source. No
    # component key collides with one today; parse class bodies with ast if that changes.
    patterns = [re.compile(rf"^\s*name\s*=\s*[\"']{re.escape(key)}[\"']", re.MULTILINE)]
    if class_name:
        patterns.append(re.compile(rf"^class {re.escape(class_name)}\b", re.MULTILINE))
    bundles = repo_root / BUNDLES_DIR
    for path in sorted(bundles.glob("*/src/**/*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if any(pattern.search(text) for pattern in patterns):
            return path.relative_to(bundles).parts[0]
    return None


def find_problems(
    base: ComponentIndex,
    merge_base: ComponentIndex,
    head: ComponentIndex,
    *,
    checker: ModuleType,
    migrations: dict[str, str],
    aliases: dict[str, str],
    repo_root: Path,
) -> list[Problem]:
    """Return the breaking changes the PR makes, plus notices for removals that still resolve."""
    problems: list[Problem] = []
    for key in sorted(base.keys() & merge_base.keys()):
        old_base = migrate_types(base[key], migrations)
        old_merge_base = migrate_types(merge_base[key], migrations)

        if key not in head:
            problems.append(_diagnose_removal(key, base[key], old_base, head, checker, migrations, aliases, repo_root))
            continue

        new = migrate_types(head[key], migrations)
        if breaks_saved_node(checker, new, old_base) and breaks_saved_node(checker, new, old_merge_base):
            # Describe against the merge base so changes that landed on base aren't attributed to the PR.
            problems.append(
                Problem("error", f"Component {key!r} changed incompatibly: {_describe_change(old_merge_base, new)}.")
            )
            continue

        transient = getattr(checker, "TRANSIENT_TEMPLATE_KEYS", frozenset())
        lost = (handle_fields(old_base, transient) & handle_fields(old_merge_base, transient)) - handle_fields(
            new, transient
        )
        if lost:
            names = ", ".join(repr(name) for name in sorted(lost))
            problems.append(
                Problem(
                    "error",
                    f"Component {key!r} input(s) {names} no longer accept connections; "
                    "updating a saved node drops edges into them.",
                )
            )
        elif old_base.get("outputs") and old_merge_base.get("outputs") and not new.get("outputs"):
            problems.append(
                Problem(
                    "notice",
                    f"Component {key!r} no longer declares static outputs; saved edges from them resolve only "
                    "if the outputs it builds at runtime keep the same names.",
                )
            )
    return problems


def _diagnose_removal(
    key: str,
    raw_entry: dict[str, Any],
    old: dict[str, Any],
    head: ComponentIndex,
    checker: ModuleType,
    migrations: dict[str, str],
    aliases: dict[str, str],
    repo_root: Path,
) -> Problem:
    module_path = (raw_entry.get("metadata") or {}).get("module") or ""
    class_name = module_path.rpartition(".")[2]

    target = aliases.get(key)
    if target in head:
        new = migrate_types(head[target], migrations)
        if breaks_saved_node(checker, new, old):
            return Problem(
                "error",
                f"Component {key!r} is aliased to {target!r}, which is incompatible: {_describe_change(old, new)}.",
            )
        return Problem("notice", f"Component {key!r} was renamed to {target!r}; saved flows resolve through the alias.")
    if target:
        external = EXTERNAL_ALIAS.match(target)
        if external and (bundle := _bundle_defining(repo_root, external.group(1), external.group(1))):
            return Problem("notice", f"Component {key!r} is aliased to {target!r} in the {bundle!r} bundle.")
        return Problem("error", f"Component {key!r} is aliased to {target!r}, which doesn't exist.")

    renamed_to = [
        other
        for other, entry in head.items()
        if module_path and (entry.get("metadata") or {}).get("module") == module_path
    ]
    if renamed_to:
        return Problem(
            "error",
            f"Component {key!r} was renamed to {renamed_to[0]!r}; saved flows that use the old name will no longer "
            f"load. Add {key!r} to LEGACY_TYPE_ALIASES in {ALIASES_FILE}.",
        )

    if module_path and _source_defines_class(repo_root, module_path):
        return Problem(
            "error",
            f"Component {key!r} is missing from the index but {module_path} still defines it. "
            "Index regeneration likely dropped it (for example, a missing optional dependency); "
            "add the `fix-index` label to rebuild the index.",
        )

    if bundle := _bundle_defining(repo_root, key, class_name):
        return Problem(
            "notice", f"Component {key!r} moved to the {bundle!r} bundle; saved flows need that bundle installed."
        )

    return Problem("error", f"Component {key!r} was removed or renamed; saved flows that use it will no longer load.")


def _escape(message: str) -> str:
    """Escape a message for a GitHub Actions workflow command."""
    return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _write_summary(lines: list[str]) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", type=Path, required=True, help="component_index.json at the base-branch tip")
    parser.add_argument("--merge-base", type=Path, required=True, help="component_index.json at the merge base")
    parser.add_argument("--head", type=Path, required=True, help="component_index.json at the PR head")
    parser.add_argument("--checker", type=Path, required=True, help="lfx/upgrade/checker.py from the base branch")
    parser.add_argument(
        "--type-migrations", type=Path, required=True, help="lfx/graph/edge/base.py (defines TYPE_MIGRATIONS)"
    )
    parser.add_argument("--repo-root", type=Path, default=Path(), help="PR head checkout, for diagnosing removals")
    parser.add_argument("--fail", action="store_true", help="exit non-zero on breaking changes and read errors")
    parser.add_argument(
        "--allow-breaking", action="store_true", help="report breaking changes as warnings (the PR is labeled)"
    )
    args = parser.parse_args(argv)
    error_level = "error" if args.fail and not args.allow_breaking else "warning"

    try:
        base, base_warnings = load_index(args.base)
        merge_base, merge_base_warnings = load_index(args.merge_base)
        head, head_warnings = load_index(args.head)
        checker = load_checker(args.checker)
        migrations = load_literal_dict(args.type_migrations, "TYPE_MIGRATIONS")
        aliases_file = args.repo_root / ALIASES_FILE
        aliases = load_literal_dict(aliases_file, "LEGACY_TYPE_ALIASES") if aliases_file.is_file() else {}
    except CheckerTooOldError as exc:
        print(f"::notice::{_escape(str(exc))}")
        return 0
    except IndexReadError as exc:
        print(f"::{'error' if args.fail else 'warning'}::{_escape(str(exc))}")
        return 2 if args.fail else 0

    for warning in base_warnings + merge_base_warnings + head_warnings:
        print(f"::warning::{_escape(warning)}")

    problems = find_problems(
        base, merge_base, head, checker=checker, migrations=migrations, aliases=aliases, repo_root=args.repo_root
    )
    if not problems:
        print("No breaking component changes found.")
        _write_summary(["## Component compatibility", "", "No breaking component changes found."])
        return 0

    for problem in problems:
        level = error_level if problem.level == "error" else "notice"
        print(f"::{level}::{_escape(problem.message)}")
    # GitHub shows only the first few annotations per step; the summary has the full list.
    print(f"{len(problems)} finding(s); see the job summary for the full list.")
    errors = [p for p in problems if p.level == "error"]
    summary = ["## Component compatibility", "", *(f"- **{p.level}**: {p.message}" for p in problems)]
    if errors and args.fail:
        summary += ["", "Add the `breaking change` label if an incompatible change is intentional."]
    _write_summary(summary)
    if errors and error_level == "error":
        print(
            f"{len(errors)} breaking component change(s) would break saved flows. "
            "If this is intentional, add the 'breaking change' label to the PR.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
