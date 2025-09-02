#!/usr/bin/env python
# scripts/ci/update_pyproject_combined.py
import sys
from pathlib import Path

from update_lf_base_dependency import update_lfx_dep_in_base
from update_pyproject_name import update_pyproject_name
from update_pyproject_name import update_uv_dep as update_name_uv_dep
from update_pyproject_version import update_pyproject_version
from update_uv_dependency import update_uv_dep as update_version_uv_dep

# Add the current directory to the path so we can import the other scripts
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))


def main():
    """Universal update script that handles both base and main updates in a single run.

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

    # First handle base package updates
    update_pyproject_name("src/backend/base/pyproject.toml", "langflow-base-nightly")
    update_name_uv_dep("pyproject.toml", "langflow-base-nightly")
    update_pyproject_version("src/backend/base/pyproject.toml", base_tag)

    # Update LFX dependency in langflow-base
    lfx_version = lfx_tag.lstrip("v")
    update_lfx_dep_in_base("src/backend/base/pyproject.toml", lfx_version)

    # Then handle main package updates
    update_pyproject_name("pyproject.toml", "langflow-nightly")
    update_name_uv_dep("pyproject.toml", "langflow-nightly")
    update_pyproject_version("pyproject.toml", main_tag)
    # Update dependency version (strip 'v' prefix if present)
    base_version = base_tag.lstrip("v")
    update_version_uv_dep(base_version)


if __name__ == "__main__":
    main()
