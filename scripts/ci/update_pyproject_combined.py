#!/usr/bin/env python
# scripts/ci/update_pyproject_combined.py
import sys
from pathlib import Path

from update_lf_base_dependency import update_base_dep, update_lfx_dep_in_base
from update_pyproject_version import update_pyproject_version
from update_uv_dependency import update_uv_dep as update_version_uv_dep

# Add the current directory to the path so we can import the other scripts
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))


def update_projects_for_nightly(main_tag: str, base_tag: str, lfx_tag: str) -> None:
    """Apply a coordinated full/core/base/LFX nightly version chain."""
    main_version = main_tag.removeprefix("v")
    base_version = base_tag.removeprefix("v")
    lfx_version = lfx_tag.removeprefix("v")

    # Lockstep invariant: full -> core -> base must use dev versions published by
    # this run. pypi_nightly_tag.py gives all three the same tag.

    # First handle base package updates (canonical name kept).
    update_pyproject_version("src/backend/base/pyproject.toml", base_version)

    # Update LFX dependency in langflow-base (exact canonical dev pin).
    update_lfx_dep_in_base("src/backend/base/pyproject.toml", lfx_version)

    # Core has the product version and delegates the service dependency surface
    # to base, including its matching optional extras.
    update_pyproject_version("src/langflow-core/pyproject.toml", main_version)
    update_base_dep("src/langflow-core/pyproject.toml", base_version)

    # Then handle main package updates (canonical name kept).
    update_pyproject_version("pyproject.toml", main_version)
    # Main delegates to the product-aligned core distribution.
    update_version_uv_dep(main_version)


def main():
    """Universal update script that handles base, core, and main in a single run.

    The packages keep their CANONICAL names (``langflow``, ``langflow-core``, ``langflow-base``) -- they are NOT
    renamed to ``*-nightly``. This script only sets the nightly ``.devN`` versions and re-pins the
    inter-package dependencies to exact canonical dev versions. See ``src/bundles/NIGHTLY.md``.

    Usage:
    update_pyproject_combined.py main <main_tag> <base_tag> <lfx_tag>
    """
    arg_count = 5
    if len(sys.argv) != arg_count:
        print("Usage:")
        print("  update_pyproject_combined.py main <main_tag> <base_tag> <lfx_tag>")
        sys.exit(1)

    mode = sys.argv[1]
    if mode != "main":
        print("Only 'main' mode is supported")
        print("Usage: update_pyproject_combined.py main <main_tag> <base_tag> <lfx_tag>")
        sys.exit(1)

    update_projects_for_nightly(sys.argv[2], sys.argv[3], sys.argv[4])


if __name__ == "__main__":
    main()
