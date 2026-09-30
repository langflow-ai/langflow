#!/usr/bin/env python3
"""CI guard: in-scope BUNDLE_API surface changes require a changelog entry.

The Bundle API contract is enumerated in ``BUNDLE_API.md`` at the repo root.
Files that contain in-scope public surface (the manifest schema, the loader's
public entry points, the typed error envelope, etc.) must not change without
a corresponding ``## Changelog`` entry being added to ``BUNDLE_API.md`` in
the same PR.

This script compares the working tree against a baseline branch and:

    1. Reads the changed files in this branch.
    2. Filters them to the in-scope set (see ``IN_SCOPE_PATHS`` below).
    3. If any in-scope file changed, asserts ``BUNDLE_API.md`` also changed
       AND that the diff includes at least one new line under a
       ``## Changelog`` heading.

Usage::

    python scripts/migrate/check_bundle_api_changelog.py
    python scripts/migrate/check_bundle_api_changelog.py --base origin/main

Exit codes:
    0 -- no in-scope changes, or in-scope changes paired with a changelog entry
    1 -- in-scope changes without a changelog entry (details to stderr)
    2 -- usage / git error
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_API_RELPATH = "BUNDLE_API.md"

# Files / directories whose changes affect the BUNDLE_API contract.
# Glob-style relative to repo root; checked via str.startswith on relative path
# OR exact match.  Keep this list deliberately tight: it only covers the
# surface enumerated in BUNDLE_API.md.
IN_SCOPE_PATHS: tuple[str, ...] = (
    # Manifest schema + JSON-Schema export
    "src/lfx/src/lfx/extension/manifest.py",
    "src/lfx/src/lfx/extension/schema.py",
    # Typed error envelope + ERROR_CODES set
    "src/lfx/src/lfx/extension/errors.py",
    # Loader subpackage public surface
    "src/lfx/src/lfx/extension/loader/__init__.py",
    "src/lfx/src/lfx/extension/loader/_orchestrator.py",
    "src/lfx/src/lfx/extension/loader/_plugins.py",
    "src/lfx/src/lfx/extension/loader/_types.py",
    # Discovery + registry
    "src/lfx/src/lfx/extension/discovery.py",
    "src/lfx/src/lfx/extension/registry.py",
    # Reload pipeline + bundle registry
    "src/lfx/src/lfx/extension/reload.py",
    "src/lfx/src/lfx/extension/bundle_registry.py",
    # HTTP surface (reload endpoint)
    "src/backend/base/langflow/api/v1/extensions.py",
    # Migration table schema
    "src/lfx/src/lfx/extension/migration/schema.py",
    # The package facade (re-exports define the surface)
    "src/lfx/src/lfx/extension/__init__.py",
    "src/lfx/src/lfx/extension/validate.py",
)


def _git(*args: str) -> str:
    """Run a git command and return stdout (or '' if it failed cleanly)."""
    try:
        result = subprocess.run(  # noqa: S603 - args is a literal list, no shell
            ["git", *args],  # noqa: S607
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        # Surface stderr to the caller; treat absent base ref as "no diff".
        if exc.stderr and "unknown revision" in exc.stderr.lower():
            return ""
        msg = f"git {' '.join(args)} failed: {exc.stderr.strip() or exc.stdout.strip()}"
        raise RuntimeError(msg) from exc
    return result.stdout


def changed_files(base: str) -> list[str]:
    """Return paths (relative to repo root) changed between ``base`` and HEAD."""
    out = _git("diff", "--name-only", base)
    return [line.strip() for line in out.splitlines() if line.strip()]


def is_in_scope(path: str) -> bool:
    return path in IN_SCOPE_PATHS or any(path.startswith(p + "/") for p in IN_SCOPE_PATHS)


def _changelog_lines_in_current_file() -> set[str]:
    """Return the set of stripped lines that live under ``## Changelog`` in the current file.

    Scans the working-tree ``BUNDLE_API.md`` (the post-edit version) so we can
    cross-reference the diff's ``+`` lines against actual section membership.
    Section ends at the next heading at the same level (``## ``) or shallower
    (``# ``), or at end-of-file.
    """
    path = REPO_ROOT / BUNDLE_API_RELPATH
    if not path.exists():
        return set()
    in_changelog = False
    found: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if stripped.startswith("## "):
            in_changelog = stripped[3:].strip().lower().startswith("changelog")
            continue
        if stripped.startswith("# "):
            # Top-level heading; section ends.
            in_changelog = False
            continue
        if in_changelog and stripped:
            found.add(stripped)
    return found


def changelog_diff_added_lines(base: str) -> list[str]:
    """Return added lines (``+`` lines) that fall under ``## Changelog`` in the new file.

    We can't rely on the diff hunk's local context to identify section
    membership (default 3 lines of context often hides the section heading).
    Instead we collect every added line from the diff and cross-reference
    against lines that actually live under ``## Changelog`` in the post-edit
    file.
    """
    diff = _git("diff", base, "--", BUNDLE_API_RELPATH)
    if not diff:
        return []
    diff_added: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            stripped = line[1:].strip()
            if stripped:
                diff_added.append(stripped)
    if not diff_added:
        return []
    changelog_lines = _changelog_lines_in_current_file()
    return [a for a in diff_added if a in changelog_lines]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Git ref to diff against (default: origin/main).",
    )
    args = parser.parse_args(argv)

    try:
        changed = changed_files(args.base)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    in_scope_changes = [p for p in changed if is_in_scope(p)]
    if not in_scope_changes:
        print("ok: no in-scope BUNDLE_API surface files changed.")
        return 0

    bundle_api_changed = BUNDLE_API_RELPATH in changed
    if not bundle_api_changed:
        print(
            f"error: in-scope BUNDLE_API surface changed but {BUNDLE_API_RELPATH} "
            f"was not updated.  Add a ## Changelog entry describing the change.",
            file=sys.stderr,
        )
        for p in in_scope_changes:
            print(f"  - {p}", file=sys.stderr)
        return 1

    try:
        added = changelog_diff_added_lines(args.base)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not added:
        print(
            f"error: in-scope BUNDLE_API surface changed and {BUNDLE_API_RELPATH} "
            f"was modified, but no new line was added under a ## Changelog heading.",
            file=sys.stderr,
        )
        for p in in_scope_changes:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(
        f"ok: {len(in_scope_changes)} in-scope file(s) changed; "
        f"{BUNDLE_API_RELPATH} has {len(added)} new changelog line(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
