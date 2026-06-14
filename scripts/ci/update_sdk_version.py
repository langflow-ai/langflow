"""Update the canonical ``langflow-sdk`` version for nightly builds.

The SDK keeps its canonical ``langflow-sdk`` name -- it is NOT renamed to ``langflow-sdk-nightly`` --
and is published as a ``.devN`` pre-release. This script only sets the nightly version.
See ``src/bundles/NIGHTLY.md``.
"""

import sys
from pathlib import Path

from update_pyproject_version import update_pyproject_version

# Add the current directory to the path so we can import the other scripts
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))


def update_sdk_for_nightly(sdk_tag: str):
    """Set the canonical ``langflow-sdk`` package version for a nightly build."""
    sdk_pyproject_path = "src/sdk/pyproject.toml"

    version = sdk_tag.lstrip("v")
    update_pyproject_version(sdk_pyproject_path, version)

    print(f"Updated langflow-sdk to nightly version {version}")


def main():
    expected_args = 2
    if len(sys.argv) != expected_args:
        print("Usage: update_sdk_version.py <sdk_tag>")
        sys.exit(1)

    sdk_tag = sys.argv[1]
    update_sdk_for_nightly(sdk_tag)


if __name__ == "__main__":
    main()
