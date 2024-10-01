import os
import sys
import re

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def update_uv_dep(base_version: str) -> None:
    """Update the langflow-base dependency in pyproject.toml."""

    pyproject_path = os.path.join(BASE_DIR, "pyproject.toml")

    # Read the pyproject.toml file content
    with open(pyproject_path, "r") as file:
        content = file.read()

    # For the main project, update the langflow-base dependency in the UV section
    pattern = re.compile(r'(dependencies\s*=\s*\[\s*\n\s*)("langflow-base==[\d.]+")')
    replacement = r'\1"langflow-base-nightly=={}"'.format(base_version)

    # Check if the pattern is found
    if not pattern.search(content):
        raise Exception(f"{pattern} UV dependency not found in {pyproject_path}")

    # Replace the matched pattern with the new one
    content = pattern.sub(replacement, content)

    # Write the updated content back to the file
    with open(pyproject_path, "w") as file:
        file.write(content)


def main() -> None:
    if len(sys.argv) != 2:
        raise Exception("specify base version")
    base_version = sys.argv[1]
    base_version = base_version.lstrip("v")
    update_uv_dep(base_version)


if __name__ == "__main__":
    main()
