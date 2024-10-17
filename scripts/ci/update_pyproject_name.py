import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent


def update_pyproject_name(pyproject_path: str, new_project_name: str) -> None:
    """Update the project name in pyproject.toml."""
    filepath = BASE_DIR / pyproject_path
    content = filepath.read_text(encoding="utf-8")

    # Regex to match the version line under [tool.poetry]
    pattern = re.compile(r'(?<=^name = ")[^"]+(?=")', re.MULTILINE)

    if not pattern.search(content):
        msg = f'Project name not found in "{filepath}"'
        raise Exception(msg)
    content = pattern.sub(new_project_name, content)

    filepath.write_text(content, encoding="utf-8")


def update_uv_dep(pyproject_path: str, new_project_name: str) -> None:
    """Update the langflow-base dependency in pyproject.toml."""
    filepath = BASE_DIR / pyproject_path
    content = filepath.read_text(encoding="utf-8")

    if new_project_name == "langflow-nightly":
        pattern = re.compile(r"langflow = \{ workspace = true \}")
        replacement = "langflow-nightly = { workspace = true }"
    elif new_project_name == "langflow-base-nightly":
        pattern = re.compile(r"langflow-base = \{ workspace = true \}")
        replacement = "langflow-base-nightly = { workspace = true }"
    else:
        msg = f"Invalid project name: {new_project_name}"
        raise ValueError(msg)

    # Updates the dependency name for uv
    if not pattern.search(content):
        msg = f"{replacement} uv dependency not found in {filepath}"
        raise Exception(msg)
    content = pattern.sub(replacement, content)
    filepath.write_text(content, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 3:
        msg = "Must specify project name and build type, e.g. langflow-nightly base"
        raise Exception(msg)
    new_project_name = sys.argv[1]
    build_type = sys.argv[2]

    if build_type == "base":
        update_pyproject_name("src/backend/base/pyproject.toml", new_project_name)
        update_uv_dep("pyproject.toml", new_project_name)
    elif build_type == "main":
        update_pyproject_name("pyproject.toml", new_project_name)
        update_uv_dep("pyproject.toml", new_project_name)
    else:
        msg = f"Invalid build type: {build_type}"
        raise ValueError(msg)


if __name__ == "__main__":
    main()
