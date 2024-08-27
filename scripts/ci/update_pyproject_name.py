import os
import sys
import re

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

def update_pyproject_file(pyproject_path: str, new_project_name: str) -> None:
    """Update the project name in pyproject.toml."""
    filepath = os.path.join(BASE_DIR, pyproject_path)
    with open(filepath, 'r') as file:
        content = file.read()

    # Regex to match the version line under [tool.poetry]
    pattern = re.compile(r'(?<=^name = ")[^"]+(?=")', re.MULTILINE)

    if not pattern.search(content):
        raise Exception(f'Project name not found in "{filepath}"')

    content = pattern.sub(new_project_name, content)

    with open(filepath, 'w') as file:
        file.write(content)

def main() -> None:
    if len(sys.argv) != 2:
        raise Exception(f'New project name not specified')
    new_project_name = sys.argv[1]
    update_pyproject_file("pyproject.toml", new_project_name)
    update_pyproject_file("src/backend/base/pyproject.toml", new_project_name)

if __name__ == "__main__":
    main()
