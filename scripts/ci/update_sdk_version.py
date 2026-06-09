"""Script to update SDK version for nightly builds."""

import sys
from pathlib import Path

from update_pyproject_name import update_pyproject_name
from update_pyproject_name import update_uv_dep as update_workspace_dep
from update_pyproject_version import update_pyproject_version

# Add the current directory to the path so we can import the other scripts
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))


def update_sdk_for_nightly(sdk_tag: str):
    """Update SDK package for nightly build."""
    sdk_pyproject_path = "src/sdk/pyproject.toml"

    update_pyproject_name(sdk_pyproject_path, "langflow-sdk-nightly")

    version = sdk_tag.lstrip("v")
    update_pyproject_version(sdk_pyproject_path, version)

    update_workspace_dep("pyproject.toml", "langflow-sdk-nightly")

    print(f"Updated SDK package to langflow-sdk-nightly version {version}")


def main():
    expected_args = 2
    if len(sys.argv) != expected_args:
        print("Usage: update_sdk_version.py <sdk_tag>")
        sys.exit(1)

    sdk_tag = sys.argv[1]
    update_sdk_for_nightly(sdk_tag)


if __name__ == "__main__":
    main()
