#!/usr/bin/env python3
"""CI gate: detect component changes in ``component_index.json`` that break saved flows.

Compares each component's index entry at the PR's merge base (as a saved node) with the PR
head (as the registry) using the repo's own upgrade checker,
``lfx.upgrade.checker.has_breaking_change``. It also reports inputs that stop accepting
connections, because the editor's Update action rebuilds the node and drops edges into them.

A component missing from the head is looked up through ``LEGACY_TYPE_ALIASES`` and then by
class name in the source, to tell renames, bundle moves and index drift from removals.

Stdlib-only so it runs on a bare runner. The workflow runs the base branch's copy of this
script, the checker and the type migrations, so a PR can't weaken the rule it is judged by.
"""

from __future__ import annotations

import argparse
import ast
import copy
import functools
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from types import ModuleType

ALIASES_FILE = Path("src/lfx/src/lfx/utils/component_aliases.py")
SOURCE_GLOBS = ("src/lfx/src/lfx/components/**/*.py", "src/bundles/*/src/**/*.py")

# Field types the editor renders as plain widgets rather than connection handles. Mirrors
# LANGFLOW_SUPPORTED_TYPES in src/frontend/src/constants/constants.ts; keep the two in sync.
FRONTEND_WIDGET_TYPES = frozenset(
    {
        "str", "bool", "float", "code", "prompt", "mustache", "file", "int", "dict", "NestedDict", "table",
        "link", "slider", "tab", "sortableList", "actionPicker", "duration", "connect", "auth", "query", "mcp",
        "tools", "data_display",
    }
)  # fmt: skip


def load_index(path: Path) -> dict[str, dict[str, Any]]:
    """Map each component key (the saved node's ``data.type``) to its index entry."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {key: entry for _category, components in data["entries"] for key, entry in components.items()}


def load_checker(path: Path) -> ModuleType:
    """Load ``lfx/upgrade/checker.py`` from a file path; its top-level imports are stdlib only."""
    spec = importlib.util.spec_from_file_location("component_compat_upgrade_checker", path)
    module = importlib.util.module_from_spec(spec)
    # Dataclasses resolve string annotations through sys.modules, so register before executing.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_literal_dict(path: Path, name: str) -> dict[str, str]:
    """Read a module-level ``name = {...}`` dict literal from a Python file without importing it."""
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        target = node.target if isinstance(node, ast.AnnAssign) else getattr(node, "targets", [None])[0]
        if isinstance(target, ast.Name) and target.id == name:
            return ast.literal_eval(node.value)
    msg = f"{path} does not define {name}"
    raise ValueError(msg)


def migrate_types(entry: dict[str, Any], migrations: dict[str, str]) -> dict[str, Any]:
    """Return a copy of ``entry`` with legacy type names mapped, as edge validation does."""
    migrated = copy.deepcopy(entry)
    for output in migrated.get("outputs") or []:
        output["types"] = [migrations.get(t, t) for t in output.get("types") or []]
    for field in (migrated.get("template") or {}).values():
        if isinstance(field, dict) and field.get("input_types"):
            field["input_types"] = [migrations.get(t, t) for t in field["input_types"]]
    return migrated


def breaks_saved_node(checker: ModuleType, new: dict[str, Any], old: dict[str, Any]) -> bool:
    """Return True if a saved node shaped like ``old`` breaks against ``new``."""
    # has_breaking_change requires equal output name sets, so drop outputs the old node never
    # had: a saved flow has no edges from them.
    old_names = {output.get("name") for output in old.get("outputs") or []}
    kept = [output for output in new.get("outputs") or [] if output.get("name") in old_names]
    if old.get("outputs") and new.get("outputs") and not kept:
        # Every output was replaced. The checker skips outputs when the registry declares none
        # (dynamic outputs, as in Run Flow), so it would miss this.
        return True
    return checker.has_breaking_change({**new, "outputs": kept}, old)


def handle_fields(entry: dict[str, Any], transient: frozenset[str]) -> set[str]:
    """Return the fields the editor draws a connection handle for.

    Mirrors ``computeDisplayHandle`` in
    src/frontend/src/CustomNodes/GenericNode/components/RenderInputParameters/utils.ts
    (outside tool mode): model fields always get a handle; other fields get one when they accept
    ``input_types`` or aren't a plain widget type, unless they have a refresh button.
    """
    return {
        key
        for key, field in (entry.get("template") or {}).items()
        if not key.startswith("_")
        and key not in transient
        and isinstance(field, dict)
        and (
            field.get("type") == "model"
            or (
                (field.get("type") not in FRONTEND_WIDGET_TYPES or field.get("input_types"))
                and not field.get("refresh_button")
            )
        )
    }


def describe_change(old: dict[str, Any], new: dict[str, Any]) -> str:
    """Summarize the differences a reviewer should look at; the checker decides breakage."""
    details = []
    new_outputs = {o.get("name"): o for o in new.get("outputs") or []}
    for output in old.get("outputs") or []:
        name = output.get("name")
        if name not in new_outputs:
            details.append(f"output {name!r} removed")
        elif lost := sorted(set(output.get("types") or []) - set(new_outputs[name].get("types") or [])):
            details.append(f"output {name!r} no longer emits {', '.join(lost)}")
    old_template, new_template = old.get("template") or {}, new.get("template") or {}
    for key, field in new_template.items():
        if not isinstance(field, dict):
            continue
        if key not in old_template and field.get("required") and field.get("value") in (None, ""):
            details.append(f"new required input {key!r} has no default")
        elif (
            field.get("input_types")
            and isinstance(old_template.get(key), dict)
            and (lost := sorted(set(old_template[key].get("input_types") or []) - set(field["input_types"])))
        ):
            details.append(f"input {key!r} no longer accepts {', '.join(lost)}")
    return "; ".join(details) or "see lfx.upgrade.checker.has_breaking_change"


@functools.cache
def class_sources(repo_root: Path) -> dict[str, Path]:
    """Map each class defined under components or bundles to its source file."""
    sources: dict[str, Path] = {}
    for glob in SOURCE_GLOBS:
        for path in sorted(repo_root.glob(glob)):
            for name in re.findall(r"^class (\w+)", path.read_text(encoding="utf-8"), re.MULTILINE):
                sources.setdefault(name, path.relative_to(repo_root))
    return sources


def diagnose_removal(key: str, entry: dict[str, Any], aliases: dict[str, str], repo_root: Path) -> tuple[str, str]:
    target = aliases.get(key, "")
    if target.startswith("ext:"):
        return "notice", f"Component {key!r} is aliased to {target!r}; saved flows need that bundle installed."
    class_name = ((entry.get("metadata") or {}).get("module") or "").rpartition(".")[2]
    source = class_sources(repo_root).get(class_name)
    if source is None:
        return "error", f"Component {key!r} was removed or renamed; saved flows that use it will no longer load."
    if source.parts[:2] == ("src", "bundles"):
        return "notice", f"Component {key!r} moved to {source}; saved flows need that bundle installed."
    return "error", (
        f"Component {key!r} is missing from the index but {source} still defines {class_name}. If it was "
        f"renamed, add {key!r} to LEGACY_TYPE_ALIASES in {ALIASES_FILE}; if index regeneration dropped it, "
        "add the `fix-index` label."
    )


def find_problems(
    merge_base: dict[str, dict[str, Any]],
    head: dict[str, dict[str, Any]],
    *,
    checker: ModuleType,
    migrations: dict[str, str],
    aliases: dict[str, str],
    repo_root: Path,
) -> list[tuple[str, str]]:
    """Return ``(level, message)`` for each breaking change the PR makes, plus notices."""
    transient = getattr(checker, "TRANSIENT_TEMPLATE_KEYS", frozenset())
    problems = []
    for key in sorted(merge_base):
        new = head.get(key) or head.get(aliases.get(key, ""))
        if new is None:
            problems.append(diagnose_removal(key, merge_base[key], aliases, repo_root))
            continue
        old, new = migrate_types(merge_base[key], migrations), migrate_types(new, migrations)
        if breaks_saved_node(checker, new, old):
            problems.append(("error", f"Component {key!r} changed incompatibly: {describe_change(old, new)}."))
        elif lost := sorted(handle_fields(old, transient) - handle_fields(new, transient)):
            problems.append(
                (
                    "error",
                    f"Component {key!r} input(s) {', '.join(map(repr, lost))} no longer accept connections; "
                    "updating a saved node drops edges into them.",
                )
            )
        elif old.get("outputs") and not new.get("outputs"):
            problems.append(
                (
                    "notice",
                    f"Component {key!r} no longer declares static outputs; saved edges from them resolve only "
                    "if the outputs it builds at runtime keep the same names.",
                )
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--merge-base", type=Path, required=True, help="component_index.json at the merge base")
    parser.add_argument("--head", type=Path, required=True, help="component_index.json at the PR head")
    parser.add_argument("--checker", type=Path, required=True, help="lfx/upgrade/checker.py from the base branch")
    parser.add_argument("--type-migrations", type=Path, required=True, help="lfx/graph/edge/base.py")
    parser.add_argument("--repo-root", type=Path, default=Path(), help="PR head checkout, for diagnosing removals")
    parser.add_argument("--fail", action="store_true", help="exit non-zero on breaking changes")
    args = parser.parse_args(argv)

    problems = find_problems(
        load_index(args.merge_base),
        load_index(args.head),
        checker=load_checker(args.checker),
        migrations=load_literal_dict(args.type_migrations, "TYPE_MIGRATIONS"),
        aliases=load_literal_dict(args.repo_root / ALIASES_FILE, "LEGACY_TYPE_ALIASES"),
        repo_root=args.repo_root,
    )
    error_level = "error" if args.fail else "warning"
    for level, message in problems:
        # Messages carry PR-controlled names; escape them so they can't inject workflow commands.
        escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::{error_level if level == 'error' else 'notice'}::{escaped}")

    # GitHub shows only the first few annotations per step; the summary has the full list.
    lines = [f"- **{level}**: {message}" for level, message in problems] or ["No breaking component changes found."]
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write("\n".join(["## Component compatibility", "", *lines]) + "\n")

    errors = sum(level == "error" for level, _ in problems)
    print(f"{len(problems)} finding(s), {errors} breaking.")
    if errors and args.fail:
        print("If an incompatible change is intentional, add the 'breaking change' label.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
