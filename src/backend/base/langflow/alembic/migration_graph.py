"""Read Alembic heads without importing migration modules."""

import argparse
import ast
import sys
from collections.abc import Iterable
from pathlib import Path

_REVISION_VARIABLES = frozenset({"revision", "down_revision"})


def revision_identifiers(source: str) -> tuple[str, tuple[str, ...]] | None:
    """Read ``(revision, down_revisions)`` from a migration module's source.

    Walks the module's top-level assignments with ``ast`` instead of matching
    lines, so bare and annotated assignments, multi-line ``down_revision``
    tuples, inline comments, docstrings, and IDs that are not hex all read the
    way Python (and therefore alembic) would see them; a later assignment
    overrides an earlier one. Returns None for a module that defines no string
    ``revision`` (e.g. a package marker).
    """
    values: dict[str, str | tuple[str, ...] | list[str] | None] = {}
    for node in ast.parse(source).body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        if isinstance(node, ast.Assign):
            names = {target.id for target in node.targets if isinstance(target, ast.Name)}
        elif isinstance(node.target, ast.Name):
            names = {node.target.id}
        else:
            continue
        for name in names & _REVISION_VARIABLES:
            values[name] = ast.literal_eval(node.value)

    revision = values.get("revision")
    if not isinstance(revision, str):
        return None
    down_revision = values.get("down_revision")
    if down_revision is None:
        return revision, ()
    if isinstance(down_revision, str):
        return revision, (down_revision,)
    return revision, tuple(down_revision)


def heads_from_sources(sources: Iterable[str]) -> set[str]:
    """Head revisions of a set of migration modules: those no other module revises."""
    identifiers = [ids for ids in map(revision_identifiers, sources) if ids is not None]
    revisions = {revision for revision, _ in identifiers}
    referenced = {down for _, down_revisions in identifiers for down in down_revisions}
    return revisions - referenced


def main() -> None:
    parser = argparse.ArgumentParser(description="Require one Alembic migration head")
    parser.add_argument("versions_dir", type=Path, help="Directory containing the Alembic revisions")
    args = parser.parse_args()

    sources = (path.read_text(encoding="utf-8") for path in args.versions_dir.glob("*.py"))
    heads = sorted(heads_from_sources(sources))
    if len(heads) != 1:
        revisions = ", ".join(heads) or "none"
        parser.exit(1, f"Expected one Alembic head, found {len(heads)} ({revisions}).\n")
    sys.stdout.write(f"Alembic head: {heads[0]}\n")


if __name__ == "__main__":
    main()
