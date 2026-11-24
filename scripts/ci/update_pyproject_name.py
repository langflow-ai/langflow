#!/usr/bin/env python

import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
ARGUMENT_NUMBER = 3


def update_pyproject_name(pyproject_path: str, new_project_name: str) -> None:
    """Update the project name in pyproject.toml.

    Also rewrites this package's own ``"<name>[extra]"`` self-references (e.g. in
    ``complete`` / ``all`` / ``image-description`` extras) to the new name. Without
    this, a renamed package's extras keep pointing at the old (PyPI) distribution
    and fail to resolve during nightly builds — e.g. the docling bundle's ``all``
    extra (``"lfx-docling[local,chunking,image-description]"``) would still demand
    the stable ``lfx-docling`` after the package became ``lfx-docling-nightly``.
    """
    filepath = BASE_DIR / pyproject_path
    content = filepath.read_text(encoding="utf-8")

    # Regex to match the name field only within the [project] section.
    # This avoids replacing 'name' in other sections like [[tool.uv.index]].
    # Pattern matches: [project] + any content (non-greedy) + name = "value".
    # The old name is captured (group 2) so we can rewrite self-references below.
    pattern = re.compile(r'(\[project\]\s*\n(?:[^\[]*?)name = ")([^"]+)(")', re.DOTALL)

    match = pattern.search(content)
    if not match:
        msg = f'Project name not found in "{filepath}"'
        raise ValueError(msg)
    old_project_name = match.group(2)
    content = pattern.sub(rf"\1{new_project_name}\3", content)

    # Rewrite this package's own `"<old name>[extra]"` self-references to the new
    # name so extras resolve against the renamed workspace member instead of
    # leaking the old name to PyPI. This generalizes the previous hardcoded
    # langflow-base / langflow handling to every renamed package (lfx, the SDK,
    # and each `lfx-*` bundle). The leading quote + escaped exact name keep
    # `"lfx[..."` from matching `"lfx-docling[..."`.
    if old_project_name != new_project_name:
        self_ref_pattern = re.compile(rf'"{re.escape(old_project_name)}\[([^\]]+)\]"')
        content = self_ref_pattern.sub(rf'"{new_project_name}[\1]"', content)

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
    elif new_project_name == "langflow-sdk-nightly":
        pattern = re.compile(r"langflow-sdk = \{ workspace = true \}")
        replacement = "langflow-sdk-nightly = { workspace = true }"
    else:
        msg = f"Invalid project name: {new_project_name}"
        raise ValueError(msg)

    # Updates the dependency name for uv
    if not pattern.search(content):
        msg = f"{replacement} uv dependency not found in {filepath}"
        raise ValueError(msg)
    content = pattern.sub(replacement, content)
    filepath.write_text(content, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != ARGUMENT_NUMBER:
        msg = "Must specify project name and build type, e.g. langflow-nightly base"
        raise ValueError(msg)
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
