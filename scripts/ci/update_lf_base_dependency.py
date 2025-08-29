#!/usr/bin/env python

import re
import sys
from pathlib import Path

import packaging.version

BASE_DIR = Path(__file__).parent.parent.parent
ARGUMENT_NUMBER = 3


def update_base_dep(pyproject_path: str, new_version: str) -> None:
    """Update the langflow-base dependency in pyproject.toml."""
    filepath = BASE_DIR / pyproject_path
    content = filepath.read_text(encoding="utf-8")

    # Updated pattern to handle PEP 440 version suffixes and both ~= and == version specifiers
    pattern = re.compile(r'("langflow-base(?:~=|==)[\d.]+(?:\.(?:post|dev|a|b|rc)\d+)*")')
    replacement = f'"langflow-base-nightly=={new_version}"'

    # Check if the pattern is found
    if not pattern.search(content):
        msg = f'langflow-base dependency not found in "{filepath}"'
        raise ValueError(msg)

    # Replace the matched pattern with the new one
    content = pattern.sub(replacement, content)
    filepath.write_text(content, encoding="utf-8")


def update_lfx_dep_in_base(pyproject_path: str, lfx_version: str) -> None:
    """Update the LFX dependency in langflow-base pyproject.toml to use nightly version."""
    filepath = BASE_DIR / pyproject_path
    content = filepath.read_text(encoding="utf-8")

    # Updated pattern to handle PEP 440 version suffixes and both ~= and == version specifiers
    pattern = re.compile(r'("lfx(?:~=|==)[\d.]+(?:\.(?:post|dev|a|b|rc)\d+)*")')
    replacement = f'"lfx-nightly=={lfx_version}"'

    # Check if the pattern is found
    if not pattern.search(content):
        msg = f'LFX dependency not found in "{filepath}"'
        raise ValueError(msg)

    # Replace the matched pattern with the new one
    content = pattern.sub(replacement, content)
    filepath.write_text(content, encoding="utf-8")


def verify_pep440(version):
    """Verify if version is PEP440 compliant.

    https://github.com/pypa/packaging/blob/16.7/packaging/version.py#L191
    """
    return packaging.version.Version(version)


def main() -> None:
    if len(sys.argv) != ARGUMENT_NUMBER:
        msg = "Usage: update_lf_base_dependency.py <base_version> <lfx_version>"
        raise ValueError(msg)
    base_version = sys.argv[1]
    lfx_version = sys.argv[2]

    # Strip "v" prefix from versions if present
    base_version = base_version.removeprefix("v")
    lfx_version = lfx_version.removeprefix("v")

    verify_pep440(base_version)
    verify_pep440(lfx_version)

    # Update langflow-base dependency in main project
    update_base_dep("pyproject.toml", base_version)

    # Update LFX dependency in langflow-base
    update_lfx_dep_in_base("src/backend/base/pyproject.toml", lfx_version)


if __name__ == "__main__":
    main()
