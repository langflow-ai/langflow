#!/usr/bin/env python
# scripts/ci/update_pyproject_combined.py
import sys
import os

# Add the current directory to the path so we can import the other scripts
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from update_pyproject_version import main as update_version
from update_pyproject_name import update_pyproject_name, update_uv_dep
from update_uv_dependency import main as update_dependency


def main():
    """
    Universal update script that handles both base and main scenarios.

    Usage:
    Base scenario: update_pyproject_combined.py base <base_tag>
    Main scenario: update_pyproject_combined.py main <main_tag> <base_tag>
    """
    if len(sys.argv) < 3:
        print("Usage:")
        print("  Base: update_pyproject_combined.py base <base_tag>")
        print("  Main: update_pyproject_combined.py main <main_tag> <base_tag>")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "base":
        if len(sys.argv) != 3:
            print("Base mode requires: <base_tag>")
            sys.exit(1)
        base_tag = sys.argv[2]

        # Direct function calls instead of using main()
        update_pyproject_name("src/backend/base/pyproject.toml", "langflow-base-nightly")
        update_uv_dep("pyproject.toml", "langflow-base-nightly")
        update_version(base_tag, "base")

    elif mode == "main":
        if len(sys.argv) != 4:
            print("Main mode requires: <main_tag> <base_tag>")
            sys.exit(1)
        main_tag = sys.argv[2]
        base_tag = sys.argv[3]

        # Direct function calls instead of using main()
        update_pyproject_name("pyproject.toml", "langflow-nightly")
        update_uv_dep("pyproject.toml", "langflow-nightly")
        update_version(main_tag, "main")
        update_dependency(base_tag)

    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
