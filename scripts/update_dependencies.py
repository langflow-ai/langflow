import re
from pathlib import Path


def read_version_from_pyproject(file_path):
    with open(file_path, "r") as file:
        for line in file:
            match = re.search(r'version = "(.*)"', line)
            if match:
                return match.group(1)
    return None


def update_pyproject_dependency(pyproject_path, version):
    pattern = re.compile(r'langflow-base = \{ path = "\./src/backend/base", develop = true \}')
    replacement = f'langflow-base = "^{version}"'
    with open(pyproject_path, "r") as file:
        content = file.read()
    content = pattern.sub(replacement, content)
    with open(pyproject_path, "w") as file:
        file.write(content)


if __name__ == "__main__":
    # Backing up files
    pyproject_path = Path(__file__).resolve().parent / "../pyproject.toml"
    pyproject_path = pyproject_path.resolve()
    with open(pyproject_path, "r") as original, open(pyproject_path.with_name("pyproject.toml.bak"), "w") as backup:
        backup.write(original.read())
    # Now backup poetry.lock
    with open(pyproject_path.with_name("poetry.lock"), "r") as original, open(
        pyproject_path.with_name("poetry.lock.bak"), "w"
    ) as backup:
        backup.write(original.read())

    # Reading version and updating pyproject.toml
    langflow_base_path = Path(__file__).resolve().parent / "../src/backend/base/pyproject.toml"
    version = read_version_from_pyproject(langflow_base_path)
    if version:
        update_pyproject_dependency(pyproject_path, version)
    else:
        print("Error: Version not found.")
