import re
import sys
from pathlib import Path

import packaging.version

BASE_DIR = Path(__file__).parent.parent.parent


def update_pyproject_version(pyproject_path: str, new_version: str) -> None:
    """Update the version in pyproject.toml."""
    filepath = BASE_DIR / pyproject_path
    content = filepath.read_text(encoding="utf-8")

    # Regex to match the version line under [tool.poetry]
    pattern = re.compile(r'(?<=^version = ")[^"]+(?=")', re.MULTILINE)

    if not pattern.search(content):
        msg = f'Project version not found in "{filepath}"'
        raise Exception(msg)

    content = pattern.sub(new_version, content)

    filepath.write_text(content, encoding="utf-8")


def verify_pep440(version):
    """Verify if version is PEP440 compliant.

    https://github.com/pypa/packaging/blob/16.7/packaging/version.py#L191
    """
    try:
        return packaging.version.Version(version)
    except packaging.version.InvalidVersion:
        raise


def main() -> None:
    if len(sys.argv) != 3:
        msg = "New version not specified"
        raise Exception(msg)
    new_version = sys.argv[1]

    # Strip "v" prefix from version if present
    new_version = new_version.removeprefix("v")

    build_type = sys.argv[2]

    verify_pep440(new_version)

    if build_type == "base":
        update_pyproject_version("src/backend/base/pyproject.toml", new_version)
    elif build_type == "main":
        update_pyproject_version("pyproject.toml", new_version)
    else:
        msg = f"Invalid build type: {build_type}"
        raise ValueError(msg)


if __name__ == "__main__":
    main()
