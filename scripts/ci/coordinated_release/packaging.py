"""Disposable source packaging for coordinated OSS releases."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .contract import identity, require


def package_version(version: str, mode: str, candidate: str | None) -> str:
    """Map the Contract v1 release identity to a PEP 440 package version."""
    return identity(version, mode, candidate).replace("-rc.", "rc")


def materialize_versions(source: str | Path, release: str, python_release: str) -> None:
    """Materialize app/base/frontend versions in a disposable source tree.

    LFX, SDK and provider bundle versions remain untouched. The frozen uv lock
    is updated only by the lock-file helper below for the two workspace package
    records.
    """
    root = Path(source)
    for relative in ("pyproject.toml", "src/backend/base/pyproject.toml"):
        path = root / relative
        text = path.read_text()
        text, count = re.subn(r'(?m)^version = "[^"]+"', f'version = "{python_release}"', text, count=1)
        require(count == 1, f"version field missing from {relative}")
        if relative == "pyproject.toml":
            text, count = re.subn(r"langflow-base==[^\", ]+", f"langflow-base=={python_release}", text, count=1)
            require(count == 1, "langflow base constraint missing")
        path.write_text(text)

    package_path = root / "src/frontend/package.json"
    package = json.loads(package_path.read_text())
    package["version"] = release
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n")
    lock_path = root / "src/frontend/package-lock.json"
    lock = json.loads(lock_path.read_text())
    lock["version"] = release
    lock.setdefault("packages", {}).setdefault("", {})["version"] = release
    lock_path.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n")
    marker = root / "src/frontend/public/coordinated-release-version.txt"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(release + "\n")


def update_frozen_uv_lock(source: str | Path, python_release: str) -> None:
    """Update only app/base workspace records in an existing uv.lock.

    This avoids a fresh dependency resolution on a release worker. The lock is
    still checked with ``uv lock --check`` by the workflow after the controlled
    workspace-record update.
    """
    path = Path(source) / "uv.lock"
    text = path.read_text()
    for package_name in ("langflow", "langflow-base"):
        pattern = re.compile(rf'(\[\[package\]\]\nname = "{re.escape(package_name)}"\nversion = )"[^"]+"')
        text, count = pattern.subn(rf'\g<1>"{python_release}"', text, count=1)
        require(count == 1, f"{package_name} workspace record missing from uv.lock")
    path.write_text(text)
