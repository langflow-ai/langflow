"""Load the operator release package under a private import name.

The probe deliberately does not put the operator checkout on ``sys.path``.  This
keeps the import isolated from any installed/deployed ``release`` package and
lets the report identify the exact source files that were exercised.
"""

# The subprocess is a fixed, read-only ``git rev-parse`` used to bind the
# evidence report to the tested checkout, never to execute operator input.
# ruff: noqa: TC003, UP035, S603, S607, TRY003, EM102

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import subprocess
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Iterator


def source_snapshot(root: Path) -> dict[str, object]:
    """Return the Git base and SHA-256 map for the operator release package."""
    package = root / "release"
    files = {}
    for path in sorted(package.glob("*.py")):
        files[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    base = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {"base_sha": base, "files": files}


@contextmanager
def load_release_package(root: Path) -> Iterator[ModuleType]:
    """Yield the current operator ``release`` package under an isolated alias."""
    package_path = root / "release"
    init = package_path / "__init__.py"
    alias = "_coordinated_operator_release_" + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(
        alias,
        init,
        submodule_search_locations=[str(package_path)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load operator package from {package_path}")
    package = importlib.util.module_from_spec(spec)
    old_dont_write = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.modules[alias] = package
    try:
        spec.loader.exec_module(package)
        yield package
    finally:
        sys.dont_write_bytecode = old_dont_write
        for name in list(sys.modules):
            if name == alias or name.startswith(alias + "."):
                del sys.modules[name]


def module(package: ModuleType, name: str) -> ModuleType:
    """Import one operator module as a child of the isolated package."""
    return importlib.import_module(package.__name__ + "." + name)
