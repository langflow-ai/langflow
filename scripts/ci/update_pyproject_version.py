import sys
import re
from pathlib import Path

import packaging.version

BASE_DIR = Path(__file__).parent.parent.parent


def update_pyproject_version(pyproject_path: str, new_version: str) -> None:
    """Update the version in pyproject.toml."""
    filepath = BASE_DIR / pyproject_path
    content = filepath.read_text()

    # Regex to match the version line under [tool.poetry]
    pattern = re.compile(r'(?<=^version = ")[^"]+(?=")', re.MULTILINE)

    if not pattern.search(content):
        raise Exception(f'Project version not found in "{filepath}"')

    content = pattern.sub(new_version, content)

    filepath.write_text(content)


def verify_pep440(version):
    """
    Verify if version is PEP440 compliant.

    https://github.com/pypa/packaging/blob/16.7/packaging/version.py#L191
    """

    try:
        return packaging.version.Version(version)
    except packaging.version.InvalidVersion as e:
        raise e


def main() -> None:
    if len(sys.argv) != 3:
        raise Exception("New version not specified")
    new_version = sys.argv[1]

    # Strip "v" prefix from version if present
    if new_version.startswith("v"):
        new_version = new_version[1:]

    build_type = sys.argv[2]

    verify_pep440(new_version)

    if build_type == "base":
        update_pyproject_version("src/backend/base/pyproject.toml", new_version)
    elif build_type == "main":
        update_pyproject_version("pyproject.toml", new_version)
    else:
        raise ValueError(f"Invalid build type: {build_type}")


if __name__ == "__main__":
    main()
