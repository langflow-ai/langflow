"""Script to update LFX version for nightly builds."""

import sys
from pathlib import Path

from update_pyproject_name import update_pyproject_name
from update_pyproject_version import update_pyproject_version

# Add the current directory to the path so we can import the other scripts
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))


def update_lfx_for_nightly(lfx_tag: str):
    """Update LFX package for nightly build.

    Args:
        lfx_tag: The nightly tag for LFX (e.g., "v0.1.0.dev0")
    """
    lfx_pyproject_path = "src/lfx/pyproject.toml"

    # Update name to lfx-nightly
    update_pyproject_name(lfx_pyproject_path, "lfx-nightly")

    # Update version (strip 'v' prefix if present)
    version = lfx_tag.lstrip("v")
    update_pyproject_version(lfx_pyproject_path, version)

    print(f"Updated LFX package to lfx-nightly version {version}")


def main():
    """Update LFX for nightly builds.

    Usage:
    update_lfx_version.py <lfx_tag>
    """
    expected_args = 2
    if len(sys.argv) != expected_args:
        print("Usage: update_lfx_version.py <lfx_tag>")
        sys.exit(1)

    lfx_tag = sys.argv[1]
    update_lfx_for_nightly(lfx_tag)


if __name__ == "__main__":
    main()
