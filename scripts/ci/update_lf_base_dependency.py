#!/usr/bin/env python

import re
import sys
from pathlib import Path

import packaging.version

BASE_DIR = Path(__file__).parent.parent.parent
ARGUMENT_NUMBER = 3


def update_base_dep(pyproject_path: str, new_version: str) -> None:
    """Pin every ``langflow-base`` requirement in a core pyproject."""
    filepath = BASE_DIR / pyproject_path
    content = filepath.read_text(encoding="utf-8")

    # Updated pattern to handle PEP 440 version suffixes, extras (e.g., [complete]),
    # ~=, ==, and >= version specifiers, and both langflow-base and langflow-base-nightly names
    # Captures extras in group 2 to preserve them in each replacement.
    pattern = re.compile(
        r'("langflow-base(?:-nightly)?((?:\[[^\]]+\])?)(?:~=|==|>=)[\d.]+(?:\.(?:post|dev|a|b|rc)\d+)*")'
    )

    # Check if the pattern is found
    match = pattern.search(content)
    if not match:
        msg = f'langflow-base dependency not found in "{filepath}"'
        raise ValueError(msg)

    # Keep the canonical `langflow-base` name; the exact `==<dev>` pin enables pre-release
    # resolution down the tree and keeps base in lockstep with the run.
    content = pattern.sub(
        lambda dependency: f'"langflow-base{dependency.group(2) or ""}=={new_version}"',
        content,
    )
    filepath.write_text(content, encoding="utf-8")


def update_lfx_dep_in_base(pyproject_path: str, lfx_version: str) -> None:
    """Update the LFX dependency in langflow-base pyproject.toml to use nightly version."""
    filepath = BASE_DIR / pyproject_path
    content = filepath.read_text(encoding="utf-8")

    # Updated pattern to handle PEP 440 version suffixes, both ~= and == version specifiers,
    # both lfx and lfx-nightly names, extras (e.g. lfx[cassandra], lfx[toolguard]), and
    # trailing markers (e.g. `; python_version < '3.14'`).
    # The extras group (1) MUST be preserved: base's `[complete]` extra pulls these
    # `lfx[extra]` references, and if they keep a `~=X.Y.0` floor while base's bare `lfx`
    # dep is pinned to `==X.Y.0.devN`, the floor (>=X.Y.0) excludes the dev release and
    # the nightly resolve becomes unsatisfiable.
    version_pattern = r"[0-9]+(?:\.[0-9]+)*(?:\.(?:post|dev|a|b|rc)\d+)*"
    pattern = re.compile(rf'"lfx(?:-nightly)?((?:\[[^\]]+\])?)(?:~=|==){version_pattern}([^"]*)"')
    # Pin base's lfx dep to the exact canonical dev version (single `lfx` distribution, no
    # `lfx-nightly`), so there is no `lfx` vs `lfx-nightly` install collision with the bundles.

    # Check if the pattern is found
    if not pattern.search(content):
        msg = f'LFX dependency not found in "{filepath}"'
        raise ValueError(msg)

    # Replace each match, preserving its own extras and environment marker.
    content = pattern.sub(lambda m: f'"lfx{m.group(1)}=={lfx_version}{m.group(2)}"', content)
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

    # Core owns the base dependency; main delegates to core.
    update_base_dep("src/langflow-core/pyproject.toml", base_version)

    # Update LFX dependency in langflow-base
    update_lfx_dep_in_base("src/backend/base/pyproject.toml", lfx_version)


if __name__ == "__main__":
    main()
