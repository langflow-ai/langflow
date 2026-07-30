#!/usr/bin/env python

import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
ARGUMENT_NUMBER = 2


def update_uv_dep(core_version: str) -> None:
    """Pin every root ``langflow-core`` requirement to a nightly version."""
    pyproject_path = BASE_DIR / "pyproject.toml"

    # Read the pyproject.toml file content
    content = pyproject_path.read_text(encoding="utf-8")

    # Main delegates its runtime and matching optional extras to langflow-core.
    # Rewrite the bare, audio, and postgresql requirements together so a nightly
    # full wheel never mixes a dev root with stable core extras.
    pattern = re.compile(
        r'"langflow-core(?:-nightly)?((?:\[[^\]]+\])?)(?:~=|==|>=)[\d.]+'
        r'(?:\.(?:post|dev|a|b|rc)\d+)*(?:,[^"]*)?"'
    )

    content, count = pattern.subn(
        lambda match: f'"langflow-core{match.group(1)}=={core_version}"',
        content,
    )
    if count == 0:
        msg = f"{pattern} UV dependency not found in {pyproject_path}"
        raise ValueError(msg)

    # Write the updated content back to the file
    pyproject_path.write_text(content, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != ARGUMENT_NUMBER:
        msg = "specify core version"
        raise ValueError(msg)
    core_version = sys.argv[1]
    core_version = core_version.lstrip("v")
    update_uv_dep(core_version)


if __name__ == "__main__":
    main()
