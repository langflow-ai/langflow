"""Script to update LFX version for nightly builds."""

import re
import sys
from pathlib import Path

from update_pyproject_name import update_pyproject_name
from update_pyproject_version import update_pyproject_version

# Add the current directory to the path so we can import the other scripts
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))

BASE_DIR = Path(__file__).parent.parent.parent


def update_lfx_workspace_dep(pyproject_path: str, new_project_name: str) -> None:
    """Update the LFX workspace dependency in pyproject.toml."""
    filepath = BASE_DIR / pyproject_path
    content = filepath.read_text(encoding="utf-8")

    if new_project_name == "lfx-nightly":
        pattern = re.compile(r"lfx = \{ workspace = true \}")
        replacement = "lfx-nightly = { workspace = true }"
    else:
        msg = f"Invalid LFX project name: {new_project_name}"
        raise ValueError(msg)

    # Updates the dependency name for uv
    if not pattern.search(content):
        msg = f"lfx workspace dependency not found in {filepath}"
        raise ValueError(msg)
    content = pattern.sub(replacement, content)
    filepath.write_text(content, encoding="utf-8")


def update_sdk_dependency_in_lfx(pyproject_path: str, sdk_version: str) -> None:
    """Update the SDK dependency in the LFX pyproject for nightly builds."""
    filepath = BASE_DIR / pyproject_path
    content = filepath.read_text(encoding="utf-8")

    pattern = re.compile(r'"langflow-sdk(?:-nightly)?(?:==|~=|>=)[\d.]+(?:\.(?:post|dev|a|b|rc)\d+)*"')
    replacement = f'"langflow-sdk-nightly=={sdk_version}"'

    if not pattern.search(content):
        msg = f"SDK dependency not found in {filepath}"
        raise ValueError(msg)

    content = pattern.sub(replacement, content)
    filepath.write_text(content, encoding="utf-8")


def update_lfx_for_nightly(lfx_tag: str, sdk_tag: str):
    """Update LFX package for nightly build.

    Args:
        lfx_tag: The nightly tag for LFX (e.g., "v0.1.0.dev0")
        sdk_tag: The nightly tag for the SDK (e.g., "v0.1.0.dev0")
    """
    lfx_pyproject_path = "src/lfx/pyproject.toml"

    # Update name to lfx-nightly
    update_pyproject_name(lfx_pyproject_path, "lfx-nightly")

    # Update version (strip 'v' prefix if present)
    version = lfx_tag.lstrip("v")
    update_pyproject_version(lfx_pyproject_path, version)

    # Update workspace dependency in root pyproject.toml
    update_lfx_workspace_dep("pyproject.toml", "lfx-nightly")

    sdk_version = sdk_tag.lstrip("v")
    update_sdk_dependency_in_lfx(lfx_pyproject_path, sdk_version)

    print(f"Updated LFX package to lfx-nightly version {version}")


def main():
    """Update LFX for nightly builds.

    Usage:
    update_lfx_version.py <lfx_tag> <sdk_tag>
    """
    expected_args = 3
    if len(sys.argv) != expected_args:
        print("Usage: update_lfx_version.py <lfx_tag> <sdk_tag>")
        sys.exit(1)

    lfx_tag = sys.argv[1]
    sdk_tag = sys.argv[2]
    update_lfx_for_nightly(lfx_tag, sdk_tag)


if __name__ == "__main__":
    main()
