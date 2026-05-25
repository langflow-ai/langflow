#!/usr/bin/env python3
"""CI guard: bare-name migration entries must map to globally-unique classes.

The extension migration table accepts three legacy reference forms:

    1. ``bare_class_name`` -- the unqualified Python identifier
       (e.g. ``OpenAIEmbeddings``).  ONLY valid if that class name appears in
       exactly one bundle folder under ``src/lfx/src/lfx/components/`` (or one
       extracted bundle under ``src/bundles/``).
    2. ``import_path`` -- always allowed.
    3. ``legacy_slot`` -- always allowed.

This script walks every Python source file under the in-tree component roots,
extracts ``class FooComponent(...)`` declarations, builds a
``class-name -> {bundle-folder}`` map, and asserts every ``bare_class_name``
entry in the migration table maps to a class found in exactly one folder.

It intentionally has zero runtime dependency on the lfx package (CI may run
before lfx is importable): the AST walk uses the stdlib only, and the
migration table is read as raw JSON.

Usage::

    python scripts/migrate/check_bare_names.py
    python scripts/migrate/check_bare_names.py --table path/to/table.json
    python scripts/migrate/check_bare_names.py --components-root path/to/components

Exit codes:
    0 -- every bare-name entry maps to a globally-unique class (or no entries)
    1 -- one or more bare-name entries are ambiguous OR map to no class
    2 -- usage / I/O / parse error
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
TABLE_RELPATH = "src/lfx/src/lfx/extension/migration/migration_table.json"
TABLE_PATH = REPO_ROOT / TABLE_RELPATH
DEFAULT_COMPONENT_ROOTS = (
    REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "components",
    REPO_ROOT / "src" / "bundles",
)

# A class is "ambiguous" if it lives in this many or more bundle folders.
_AMBIGUITY_THRESHOLD = 2


def _iter_component_files(roots: Iterable[Path]) -> Iterable[Path]:
    """Yield every ``.py`` file under each root, skipping caches and dunders."""
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            # Skip __pycache__ and __init__ scaffolding; class declarations
            # in __init__.py are re-exports and would double-count the bundle.
            if "__pycache__" in path.parts:
                continue
            if path.name == "__init__.py":
                continue
            yield path


def _bundle_folder_for(file_path: Path, roots: Iterable[Path]) -> str | None:
    """Return the bundle-folder name owning ``file_path`` (e.g. ``openai``).

    The "bundle folder" is the directory immediately under one of the roots.
    Returns None if the file is not under any of the given roots.
    """
    for root in roots:
        try:
            rel = file_path.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        if not rel.parts:
            return None
        return rel.parts[0]
    return None


def _classes_in_file(file_path: Path) -> list[str]:
    """Return the names of every top-level ``class`` declared in ``file_path``."""
    try:
        source = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"could not read {file_path}: {exc}"
        raise RuntimeError(msg) from exc
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as exc:
        msg = f"syntax error in {file_path}: {exc}"
        raise RuntimeError(msg) from exc
    return [node.name for node in tree.body if isinstance(node, ast.ClassDef)]


def build_class_to_bundles(roots: Iterable[Path]) -> dict[str, set[str]]:
    """Walk every component file under ``roots`` and map class names to bundles.

    Returns a dict ``{class_name: {bundle_folder, ...}}``.  A class found in
    exactly one bundle folder has a singleton set; an ambiguous class has
    multiple folders in its set.
    """
    roots = tuple(roots)
    mapping: dict[str, set[str]] = defaultdict(set)
    for file_path in _iter_component_files(roots):
        bundle = _bundle_folder_for(file_path, roots)
        if bundle is None:
            continue
        for class_name in _classes_in_file(file_path):
            mapping[class_name].add(bundle)
    return dict(mapping)


def _bare_name_entries(table: dict) -> list[dict]:
    entries = table.get("entries", [])
    if not isinstance(entries, list):
        msg = "migration table 'entries' must be a list"
        raise TypeError(msg)
    return [e for e in entries if isinstance(e, dict) and e.get("bare_class_name") is not None]


def _ambiguous_bare_name_set(table: dict) -> set[str]:
    """Return the set of bare names registered as ``ambiguous_bare_names``.

    These are the names the rewriter surfaces ``component-name-ambiguous`` for;
    any bare name found in 2+ bundle folders must be either here OR have a
    specific import_path entry per variant so saved flows still resolve.
    """
    ambig = table.get("ambiguous_bare_names", [])
    if not isinstance(ambig, list):
        msg = "migration table 'ambiguous_bare_names' must be a list"
        raise TypeError(msg)
    out: set[str] = set()
    for entry in ambig:
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            out.add(entry["name"])
    return out


def find_violations(
    bare_name_entries: list[dict],
    class_to_bundles: dict[str, set[str]],
) -> list[str]:
    """Return human-readable violation messages, one per bad entry."""
    violations: list[str] = []
    for entry in bare_name_entries:
        name = entry["bare_class_name"]
        bundles = class_to_bundles.get(name, set())
        if not bundles:
            violations.append(
                f"bare_class_name {name!r} -> {entry.get('target')!r}: "
                f"no class named {name} found in any bundle folder.  Either "
                f"the class was removed without retiring the entry, or the "
                f"name is misspelled."
            )
            continue
        if len(bundles) > 1:
            sorted_bundles = sorted(bundles)
            violations.append(
                f"bare_class_name {name!r} -> {entry.get('target')!r}: "
                f"ambiguous; appears in {len(bundles)} bundle folders "
                f"({', '.join(sorted_bundles)}).  Remove the bare-name entry; "
                f"saved flows referencing this class by bare form must be "
                f"resaved with a namespace.  Add an ``import_path`` entry "
                f"per legacy location instead."
            )
    return violations


def find_unregistered_ambiguities(
    class_to_bundles: dict[str, set[str]],
    ambiguous_names: set[str],
    *,
    only_components: bool = True,
) -> list[str]:
    """Return one message per ambiguous Component class missing from the marker list.

    Per the LE-1020 contract, a bare class name that exists in 2+ bundle
    folders must surface ``component-name-ambiguous`` at flow-load time.
    The rewriter's only durable signal is the ``ambiguous_bare_names``
    list; without an entry there the value falls through to
    ``component-not-found-with-hint``, which is the wrong code.

    When ``only_components`` is true (the default) we restrict the check to
    classes whose name ends in ``Component`` -- that's the population a
    saved flow would reference.  Utility schemas / method enums that share
    a class name across bundles are not reachable from a flow JSON, so we
    do not require markers for them.
    """
    out: list[str] = []
    for class_name, bundles in sorted(class_to_bundles.items()):
        if len(bundles) < _AMBIGUITY_THRESHOLD:
            continue
        if only_components and not class_name.endswith("Component"):
            continue
        if class_name in ambiguous_names:
            continue
        sorted_bundles = sorted(bundles)
        out.append(
            f"ambiguous Component class {class_name!r} appears in "
            f"{len(bundles)} bundle folders ({', '.join(sorted_bundles)}) "
            f"but is not registered in ``ambiguous_bare_names``.  Add an "
            f"entry so the deserializer surfaces ``component-name-ambiguous`` "
            f"with the candidate targets, instead of falling through to "
            f"``component-not-found-with-hint``."
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--table",
        type=Path,
        default=TABLE_PATH,
        help=f"Path to migration_table.json (default: {TABLE_RELPATH}).",
    )
    parser.add_argument(
        "--components-root",
        type=Path,
        action="append",
        default=None,
        help=(
            "Component-root directory to scan.  May be passed multiple times.  "
            "Defaults to src/lfx/src/lfx/components and src/bundles."
        ),
    )
    args = parser.parse_args(argv)

    if not args.table.exists():
        print(f"error: migration table not found at {args.table}", file=sys.stderr)
        return 2
    try:
        table = json.loads(args.table.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: migration table at {args.table} is not valid JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(table, dict):
        print(f"error: migration table at {args.table} must be a JSON object", file=sys.stderr)
        return 2

    try:
        bare_entries = _bare_name_entries(table)
        ambiguous_names = _ambiguous_bare_name_set(table)
    except TypeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    roots = args.components_root if args.components_root else list(DEFAULT_COMPONENT_ROOTS)
    try:
        class_to_bundles = build_class_to_bundles(roots)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    violations: list[str] = []
    if bare_entries:
        violations.extend(find_violations(bare_entries, class_to_bundles))

    # Always run the ambiguity-coverage check: any Component class found in
    # 2+ bundle folders must have an ``ambiguous_bare_names`` entry so the
    # deserializer surfaces the right typed code.
    violations.extend(find_unregistered_ambiguities(class_to_bundles, ambiguous_names))

    if violations:
        print(
            "error: bare-name migration coverage failed; refusing the following:",
            file=sys.stderr,
        )
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(
        f"ok: {len(bare_entries)} bare_class_name entries checked, "
        f"{len(ambiguous_names)} ambiguous-bare-name markers checked, "
        f"against {sum(len(b) for b in class_to_bundles.values())} class declarations."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
