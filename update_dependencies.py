import re

def read_version_from_pyproject(file_path):
    with open(file_path, 'r') as file:
        for line in file:
            match = re.search(r'version = "(.*)"', line)
            if match:
                return match.group(1)
    return None

def update_pyproject_dependency(pyproject_path, version):
    pattern = re.compile(r'langflow-base = \{ path = "\./src/backend/base", develop = true \}')
    replacement = f'langflow-base = "^{version}"'
    with open(pyproject_path, 'r') as file:
        content = file.read()
    content = pattern.sub(replacement, content)
    with open(pyproject_path, 'w') as file:
        file.write(content)

if __name__ == "__main__":
    # Backing up files
    with open('pyproject.toml', 'r') as original, open('pyproject.toml2', 'w') as backup:
        backup.write(original.read())
    with open('poetry.lock', 'r') as original, open('poetry.lock2', 'w') as backup:
        backup.write(original.read())

    # Reading version and updating pyproject.toml
    version = read_version_from_pyproject('./src/backend/base/pyproject.toml')
    if version:
        update_pyproject_dependency('pyproject.toml', version)
    else:
        print("Error: Version not found.")
