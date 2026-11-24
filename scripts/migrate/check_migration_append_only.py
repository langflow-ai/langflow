#!/usr/bin/env python3
"""CI guard: the extension migration table is append-only.

Compares the working-tree version of ``migration_table.json`` against the
``main`` (or ``--base``) branch and fails the build if any entry was removed
or mutated.  Adding new entries is allowed; reordering existing entries is
allowed (the runtime does not care about order); changing the ``target``,
``legacy_*`` field, or the value any entry maps from is **not**.

The same invariant applies to the ``ambiguous_bare_names`` list: a marker
may not be removed once published, and its ``candidates`` list may only
grow -- shrinking it would regress a saved flow that previously surfaced
``component-name-ambiguous`` to ``component-not-found-with-hint``.

Usage::

    python scripts/migrate/check_migration_append_only.py
    python scripts/migrate/check_migration_append_only.py --base origin/main
    python scripts/migrate/check_migration_append_only.py --baseline path/to/old.json

Exit codes:
    0 -- table is append-only against the baseline (or baseline is empty)
    1 -- removal or mutation detected (details printed to stderr)
    2 -- usage / I/O error
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TABLE_RELPATH = "src/lfx/src/lfx/extension/migration/migration_table.json"
TABLE_PATH = REPO_ROOT / TABLE_RELPATH


# A migration entry is uniquely identified by the (legacy_form_kind, legacy_value)
# pair.  We re-derive that here so this script has no runtime dependency on
# the lfx package (CI may run before lfx is importable).
def _entry_key(entry: dict) -> tuple[str, str]:
    if entry.get("bare_class_name") is not None:
        return ("bare_class_name", entry["bare_class_name"])
    if entry.get("import_path") is not None:
        return ("import_path", entry["import_path"])
    if entry.get("legacy_slot") is not None:
        return ("legacy_slot", entry["legacy_slot"])
    msg = (
        f"Migration entry has no populated legacy form: {entry!r}. "
        "Each entry must populate exactly one of "
        "bare_class_name / import_path / legacy_slot."
    )
    raise ValueError(msg)


def _git_show(ref: str, relpath: str) -> str | None:
    """Return the contents of ``relpath`` at ``ref``, or ``None`` if absent.

    Absence is the common-case on initial introduction of the table file:
    the baseline simply doesn't have the file yet, in which case there is
    nothing to compare against and the check trivially passes.
    """
    try:
        completed = subprocess.run(  # noqa: S603 - git invoked with a fixed argv list
            ["git", "show", f"{ref}:{relpath}"],  # noqa: S607 - git resolves via PATH like every CI runner
            check=False,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
    except FileNotFoundError:  # git not on PATH
        msg = "git is not available; cannot check append-only invariant."
        raise SystemExit(msg) from None
    if completed.returncode != 0:
        # Most likely: file not present at base ref.  We treat that as
        # "no baseline" and return None.
        return None
    return completed.stdout


def _parse(raw: str, *, source: str) -> tuple[list[dict], list[dict]]:
    """Return ``(entries, ambiguous_bare_names)`` from a migration-table JSON.

    Both lists default to empty when the field is absent so this script can
    compare across baselines that pre-date a given field.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {source}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    if not isinstance(data, dict):
        print(f"error: {source} top-level value must be an object", file=sys.stderr)
        raise SystemExit(2)
    entries = data.get("entries", [])
    if not isinstance(entries, list):
        print(f"error: {source} entries field must be a list", file=sys.stderr)
        raise SystemExit(2)
    ambig = data.get("ambiguous_bare_names", [])
    if not isinstance(ambig, list):
        print(f"error: {source} ambiguous_bare_names field must be a list", file=sys.stderr)
        raise SystemExit(2)
    return entries, ambig


def _compare(baseline: list[dict], current: list[dict]) -> list[str]:
    """Return human-readable violations; empty list means clean."""
    violations: list[str] = []
    current_by_key: dict[tuple[str, str], dict] = {}
    for entry in current:
        try:
            key = _entry_key(entry)
        except ValueError as exc:
            violations.append(str(exc))
            continue
        if key in current_by_key:
            violations.append(f"duplicate entry in current table: {key[0]}={key[1]!r}")
            continue
        current_by_key[key] = entry

    for entry in baseline:
        try:
            key = _entry_key(entry)
        except ValueError as exc:
            # Baseline shouldn't be malformed, but if it is, surface the issue
            # instead of using it to silently approve removals.
            violations.append(f"baseline entry malformed: {exc}")
            continue
        match = current_by_key.get(key)
        if match is None:
            violations.append(
                f"entry removed: {key[0]}={key[1]!r} -> {entry.get('target')!r} (added in {entry.get('added_in')!r})"
            )
            continue
        # Mutation check: target and the populated legacy field must be
        # byte-identical.  ``added_in`` is allowed to drift only if the
        # baseline didn't carry it (older format); we don't enforce here.
        if match.get("target") != entry.get("target"):
            violations.append(
                f"entry target changed: {key[0]}={key[1]!r}: {entry.get('target')!r} -> {match.get('target')!r}"
            )
    return violations


def _ambig_name(entry: dict) -> str | None:
    """Return the bare-name key of an ambiguity marker, or ``None`` if malformed."""
    name = entry.get("name")
    return name if isinstance(name, str) else None


def _ambig_candidates(entry: dict) -> set[str]:
    raw = entry.get("candidates", [])
    if not isinstance(raw, list):
        return set()
    return {c for c in raw if isinstance(c, str)}


def _compare_ambiguous(baseline: list[dict], current: list[dict]) -> list[str]:
    """Return human-readable violations for ambiguous_bare_names changes.

    Append-only contract:
        * No marker may be removed once published.
        * The candidate set may only grow; removing a candidate would
          regress a saved flow that previously surfaced
          ``component-name-ambiguous`` (with that target as one of the
          fix-hint options) to ``component-not-found-with-hint``.
    """
    violations: list[str] = []
    current_by_name: dict[str, dict] = {}
    for entry in current:
        name = _ambig_name(entry)
        if name is None:
            violations.append(f"current ambiguous_bare_names entry malformed (no name): {entry!r}")
            continue
        if name in current_by_name:
            violations.append(f"duplicate ambiguous_bare_names entry in current table: name={name!r}")
            continue
        current_by_name[name] = entry

    for entry in baseline:
        name = _ambig_name(entry)
        if name is None:
            violations.append(f"baseline ambiguous_bare_names entry malformed (no name): {entry!r}")
            continue
        match = current_by_name.get(name)
        if match is None:
            violations.append(
                f"ambiguous_bare_names marker removed: name={name!r} (added in {entry.get('added_in')!r})"
            )
            continue
        baseline_candidates = _ambig_candidates(entry)
        current_candidates = _ambig_candidates(match)
        missing = baseline_candidates - current_candidates
        if missing:
            violations.append(f"ambiguous_bare_names candidates shrunk for name={name!r}: removed {sorted(missing)!r}")
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Git ref to compare against (default: origin/main).",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help=("Read the baseline from a local file instead of git.  Useful for unit-testing this script."),
    )
    parser.add_argument(
        "--current",
        type=Path,
        default=TABLE_PATH,
        help=f"Path to the current table (default: {TABLE_RELPATH}).",
    )
    args = parser.parse_args(argv)

    if not args.current.exists():
        print(f"error: current table not found at {args.current}", file=sys.stderr)
        return 2
    current_raw = args.current.read_text(encoding="utf-8")

    if args.baseline is not None:
        if not args.baseline.exists():
            print(f"error: baseline file not found at {args.baseline}", file=sys.stderr)
            return 2
        baseline_raw = args.baseline.read_text(encoding="utf-8")
    else:
        baseline_raw = _git_show(args.base, TABLE_RELPATH)

    if baseline_raw is None:
        # No baseline -> nothing to compare; this branch introduces the
        # table for the first time.
        print(f"no baseline migration table at {args.base}:{TABLE_RELPATH}; nothing to compare.")
        return 0

    baseline_entries, baseline_ambig = _parse(baseline_raw, source=f"{args.base}:{TABLE_RELPATH}")
    current_entries, current_ambig = _parse(current_raw, source=str(args.current))
    violations = _compare(baseline_entries, current_entries)
    violations.extend(_compare_ambiguous(baseline_ambig, current_ambig))

    if violations:
        print(
            "error: migration table is append-only; refusing the following changes:",
            file=sys.stderr,
        )
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print(
        f"ok: migration table is append-only "
        f"(entries: {len(current_entries)}, +{len(current_entries) - len(baseline_entries)}; "
        f"ambiguous_bare_names: {len(current_ambig)}, +{len(current_ambig) - len(baseline_ambig)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
