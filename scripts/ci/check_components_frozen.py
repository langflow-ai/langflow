#!/usr/bin/env python3
"""CI gate: freeze the top-level provider directories under ``lfx/components/``.

After the bundle metapackage split (1.11), no NEW top-level subdirectory may be
added to ``src/lfx/src/lfx/components/`` -- new providers go to the
``lfx-bundles`` metapackage (``src/bundles/lfx-bundles/src/lfx_bundles/<provider>/``)
or a graduated ``lfx-<provider>`` package, never in-tree.

This is an **additions-only** gate: it fails when the live listing contains a
top-level directory that is not in the committed baseline
(``frozen_component_dirs.txt``). Removals are allowed and never fail the gate --
the bulk move (PR-6) replaces each moved provider with a near-empty import
shim that keeps the directory present, and the M4 shim cleanup later removes
those dirs, which only shrinks the set.

Stdlib-only by design so it runs on a bare runner without ``uv sync``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# scripts/ci/check_components_frozen.py -> repo root is two parents up.
REPO_ROOT = Path(__file__).resolve().parents[2]
COMPONENTS_DIR = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "components"
BASELINE_FILE = Path(__file__).resolve().parent / "frozen_component_dirs.txt"

# Directories that are package machinery, not providers; never counted.
_SKIP = {"__pycache__"}


def _current_dirs() -> set[str]:
    """Top-level provider directories present in the working tree."""
    return {
        entry.name
        for entry in COMPONENTS_DIR.iterdir()
        if entry.is_dir() and entry.name not in _SKIP and not entry.name.startswith(".")
    }


def _baseline_dirs() -> set[str]:
    """The frozen baseline set (blank lines and ``#`` comments ignored)."""
    lines = BASELINE_FILE.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")}


def main() -> int:
    if not COMPONENTS_DIR.is_dir():
        print(f"::error:: components directory not found: {COMPONENTS_DIR}", file=sys.stderr)
        return 1
    if not BASELINE_FILE.is_file():
        print(f"::error:: frozen baseline not found: {BASELINE_FILE}", file=sys.stderr)
        return 1

    current = _current_dirs()
    baseline = _baseline_dirs()

    new_dirs = sorted(current - baseline)
    if new_dirs:
        print(
            "::error:: src/lfx/src/lfx/components/ is frozen: no new top-level provider "
            "directory may be added in-tree.\n"
            f"  Offending new directories: {new_dirs}\n"
            "  New providers go to the lfx-bundles metapackage "
            "(src/bundles/lfx-bundles/src/lfx_bundles/<provider>/) or a graduated "
            "lfx-<provider> package -- not src/lfx/src/lfx/components/.\n"
            f"  If a directory is a deliberate exception, add it to {BASELINE_FILE.name}.",
            file=sys.stderr,
        )
        return 1

    removed = sorted(baseline - current)
    if removed:
        # Informational only: shim cleanup (M4) legitimately shrinks the set.
        print(f"note: {len(removed)} baselined component dir(s) no longer present (allowed): {removed}")
    print(f"OK: {len(current)} top-level component dir(s); no additions beyond the frozen baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
