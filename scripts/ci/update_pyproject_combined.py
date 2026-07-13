#!/usr/bin/env python
# scripts/ci/update_pyproject_combined.py
import sys
from pathlib import Path

from update_lf_base_dependency import (
    update_langflow_services_dep_in_base,
    update_lfx_dep_in_base,
    update_lfx_dep_in_services,
)
from update_pyproject_version import update_pyproject_version
from update_uv_dependency import update_uv_dep as update_version_uv_dep

# Add the current directory to the path so we can import the other scripts
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))


def main():
    """Universal update script that handles both base and main updates in a single run.

    The packages keep their CANONICAL names (``langflow``, ``langflow-base``,
    ``langflow-services``) -- they are NOT renamed to ``*-nightly``. This script only
    sets the nightly ``.devN`` versions and re-pins the inter-package dependencies to
    exact canonical dev versions. See ``src/bundles/NIGHTLY.md``.

    ``langflow-services`` versions with ``main_tag`` (1.x axis, same as langflow/lfx).
    ``langflow-base`` versions with ``base_tag`` (nightlies remap base onto the root
    axis so ``base_tag == main_tag``; stable releases keep base on 0.x).

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

    main_tag = sys.argv[2]
    base_tag = sys.argv[3]
    lfx_tag = sys.argv[4]

    # Lockstep invariant: langflow-base's published dev version (set here from `base_tag`) and
    # langflow's exact `==` pin on it (set below from the same `base_tag`) MUST come from the same
    # value, so the latest nightly `langflow` always pins a base version published in the same run.
    # `pypi_nightly_tag.py` makes the main and base tags identical; keep both writes sourced from
    # `base_tag` or the pin can reference a version that was never published.

    # First handle base package updates (canonical name kept).
    update_pyproject_version("src/backend/base/pyproject.toml", base_tag)
    # langflow-services versions with langflow / lfx (main_tag on the 1.x axis).
    update_pyproject_version("src/langflow-services/pyproject.toml", main_tag)

    # Update LFX dependency in langflow-base and langflow-services (exact canonical dev pin).
    lfx_version = lfx_tag.lstrip("v")
    update_lfx_dep_in_base("src/backend/base/pyproject.toml", lfx_version)
    update_lfx_dep_in_services("src/langflow-services/pyproject.toml", lfx_version)
    # Pin services from the root/main tag (1.x), not the remapped base tag (0.x).
    update_langflow_services_dep_in_base(
        "src/backend/base/pyproject.toml",
        main_tag.lstrip("v"),
    )

    # Then handle main package updates (canonical name kept).
    update_pyproject_version("pyproject.toml", main_tag)
    # Update langflow-base dependency version (strip 'v' prefix if present).
    base_version = base_tag.lstrip("v")
    update_version_uv_dep(base_version)


if __name__ == "__main__":
    main()
