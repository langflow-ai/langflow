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
    # Updated pattern to handle PEP 440 version suffixes, extras (e.g., [complete]),
    # and both ~= and == version specifiers
    # Also handles both langflow-base and langflow-base-nightly names
    # Captures extras in group 3 to preserve them in the replacement
    pattern = re.compile(
        r'(dependencies\s*=\s*\[\s*\n\s*)("langflow-base(?:-nightly)?((?:\[[^\]]+\])?)(?:~=|==)[\d.]+(?:\.(?:post|dev|a|b|rc)\d+)*")'
    )

    # Check if the pattern is found
    match = pattern.search(content)
    if not match:
        msg = f"{pattern} UV dependency not found in {pyproject_path}"
        raise ValueError(msg)

    # Extract extras if present (e.g., "[complete]")
    extras = match.group(3) if match.group(3) else ""
    replacement = rf'\1"langflow-base-nightly{extras}=={base_version}"'

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
