#!/usr/bin/env python3
"""CI gate: detect component changes in ``component_index.json`` that break saved flows.

Saved flows reference components by their index name and connect edges by input and
output ``name``. Removing or renaming any of these breaks existing flows, so this
gate fails when a PR removes a component, an input field, or an output.

The comparison is three-way. A name counts as removed by the PR only when it is
present in both the base-branch tip and the PR's merge base but absent from the
PR head. This keeps the gate from blaming a PR for changes that landed on the
base branch after the PR branched (for example, a component deleted on the base
branch after the PR merged it in).

Pass ``--allow-breaking`` (the workflow sets it when the PR carries the
``breaking change`` label) to report the changes as warnings without failing.

Stdlib-only by design so it runs on a bare runner without ``uv sync``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Template keys that are component machinery, not user-facing inputs.
_NON_INPUT_TEMPLATE_KEYS = {"_type", "code"}

ComponentShape = dict[str, dict[str, set[str]]]


def load_index(path: Path) -> ComponentShape:
    """Map each component name (the index key saved flows match on) to its input and output names."""
    data = json.loads(path.read_text(encoding="utf-8"))
    shape: ComponentShape = {}
    for _category, components in data["entries"]:
        for component_name, component in components.items():
            if component_name in shape:
                msg = f"{path}: component {component_name!r} appears in more than one category"
                raise ValueError(msg)
            shape[component_name] = {
                "inputs": set(component["template"]) - _NON_INPUT_TEMPLATE_KEYS,
                "outputs": {output["name"] for output in component["outputs"]},
            }
    return shape


def find_breaking_changes(base: ComponentShape, merge_base: ComponentShape, head: ComponentShape) -> list[str]:
    """Return a message for each component, input, or output the PR removed."""
    problems: list[str] = []
    for component_name in sorted(base.keys() & merge_base.keys()):
        if component_name not in head:
            problems.append(f"Component {component_name!r} was removed or renamed.")
            continue
        for kind in ("inputs", "outputs"):
            removed = (base[component_name][kind] & merge_base[component_name][kind]) - head[component_name][kind]
            problems.extend(
                f"{component_name}: {kind[:-1]} {name!r} was removed or renamed." for name in sorted(removed)
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", type=Path, required=True, help="component_index.json at the base-branch tip")
    parser.add_argument("--merge-base", type=Path, required=True, help="component_index.json at the merge base")
    parser.add_argument("--head", type=Path, required=True, help="component_index.json at the PR head")
    parser.add_argument(
        "--allow-breaking",
        action="store_true",
        help="report breaking changes as warnings instead of failing",
    )
    args = parser.parse_args(argv)

    problems = find_breaking_changes(load_index(args.base), load_index(args.merge_base), load_index(args.head))
    if not problems:
        print("No breaking component changes found.")
        return 0

    level = "warning" if args.allow_breaking else "error"
    for problem in problems:
        print(f"::{level}::{problem}")
    if args.allow_breaking:
        print(f"{len(problems)} breaking component change(s) allowed by the 'breaking change' label.")
        return 0
    print(
        f"{len(problems)} breaking component change(s) would break saved flows. "
        "If this is intentional, add the 'breaking change' label to the PR.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
