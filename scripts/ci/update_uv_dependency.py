#!/usr/bin/env python

import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
ARGUMENT_NUMBER = 2


def update_uv_dep(base_version: str) -> None:
    """Update the langflow-base dependency in pyproject.toml."""
    pyproject_path = BASE_DIR / "pyproject.toml"

    # Read the pyproject.toml file content
    content = pyproject_path.read_text(encoding="utf-8")

    # For the main project, update the langflow-base dependency in the UV section
    # Updated pattern to handle PEP 440 version suffixes and both ~= and == version specifiers
    pattern = re.compile(
        r'(dependencies\s*=\s*\[\s*\n\s*)("langflow-base(?:~=|==)[\d.]+(?:\.(?:post|dev|a|b|rc)\d+)*")'
    )
    replacement = rf'\1"langflow-base-nightly=={base_version}"'

    # Check if the pattern is found
    if not pattern.search(content):
        msg = f"{pattern} UV dependency not found in {pyproject_path}"
        raise ValueError(msg)

    # Replace the matched pattern with the new one
    content = pattern.sub(replacement, content)

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
