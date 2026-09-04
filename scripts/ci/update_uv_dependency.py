#!/usr/bin/env python

import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
ARGUMENT_NUMBER = 2


def update_uv_dep(base_version: str) -> None:
    """Pin every root ``langflow-base`` requirement to a nightly version."""
    pyproject_path = BASE_DIR / "pyproject.toml"

    # Read the pyproject.toml file content
    content = pyproject_path.read_text(encoding="utf-8")

    # Main delegates its runtime and matching optional extras to langflow-base.
    # Rewrite the bare, audio, and postgresql requirements together so a nightly
    # full wheel never mixes a dev root with stable base extras.
    pattern = re.compile(
        r'"langflow-base(?:-nightly)?((?:\[[^\]]+\])?)(?:~=|==|>=)[\d.]+'
        r'(?:\.(?:post|dev|a|b|rc)\d+)*(?:,[^"]*)?"'
    )

    content, count = pattern.subn(
        lambda match: f'"langflow-base{match.group(1)}=={base_version}"',
        content,
    )
    if count == 0:
        msg = f"{pattern} UV dependency not found in {pyproject_path}"
        raise ValueError(msg)

    # Write the updated content back to the file
    pyproject_path.write_text(content, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != ARGUMENT_NUMBER:
        msg = "specify base version"
        raise ValueError(msg)
    base_version = sys.argv[1]
    base_version = base_version.lstrip("v")
    update_uv_dep(base_version)


if __name__ == "__main__":
    main()
