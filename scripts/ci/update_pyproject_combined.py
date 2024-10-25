#!/usr/bin/env python
# scripts/ci/update_pyproject_combined.py

import sys
from scripts.ci.update_pyproject_version import main as update_version
from scripts.ci.update_pyproject_name import main as update_name
from scripts.ci.update_uv_dependency import main as update_dependency


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
        update_name("langflow-base-nightly", "base")
        update_version(base_tag, "base")

    elif mode == "main":
        if len(sys.argv) != 4:
            print("Main mode requires: <main_tag> <base_tag>")
            sys.exit(1)
        main_tag = sys.argv[2]
        base_tag = sys.argv[3]
        update_version(main_tag, "main")
        update_name("langflow-nightly", "main")
        update_dependency(base_tag)

    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
