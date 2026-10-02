"""Fail if the application lock or universal Mend export reintroduces Chroma.

The separately built migration helper is outside the application workspace and
has its own dependency inventory and security disposition.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import tomllib

FORBIDDEN_PACKAGES = {"chromadb", "langchain-chroma", "agent-lifecycle-toolkit"}


def check_inventory(root: Path) -> None:
    """Reject retired SDK distributions in an installed application artifact."""
    uv = shutil.which("uv")
    if uv is None:
        msg = "uv is required to verify the universal application dependency export."
        raise RuntimeError(msg)
    lock = tomllib.loads((root / "uv.lock").read_text())
    names = {package["name"].lower().replace("_", "-") for package in lock["package"]}
    forbidden = names & FORBIDDEN_PACKAGES
    if forbidden:
        msg = f"Retired dependencies remain in the application lock: {sorted(forbidden)}"
        raise RuntimeError(msg)

    # Match the security scanner's full scope, including optional groups and
    # extras. Checking only the default environment misses transitive parents.
    exported = subprocess.run(  # noqa: S603 -- trusted CI executable and fixed arguments, no shell
        [
            uv,
            "export",
            "--frozen",
            "--all-packages",
            "--all-extras",
            "--all-groups",
            "--format",
            "requirements-txt",
            "--no-hashes",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    export_names = {
        match.group(1).lower().replace("_", "-")
        for line in exported.splitlines()
        if (match := re.match(r"^([A-Za-z0-9_.-]+)(?:\[|[=<>!~; ])", line))
    }
    forbidden = export_names & FORBIDDEN_PACKAGES
    if forbidden:
        msg = f"Retired dependencies remain in the universal export: {sorted(forbidden)}"
        raise RuntimeError(msg)
    if not {"apsw", "sqlite-vec"} <= export_names:
        msg = "The pinned SQLite runtime is absent from the universal export."
        raise RuntimeError(msg)

    base = tomllib.loads((root / "src/backend/base/pyproject.toml").read_text())
    if not any(requirement.startswith("lfx[sqlite]") for requirement in base["project"]["dependencies"]):
        msg = "langflow-base must install the SQLite runtime by default."
        raise RuntimeError(msg)
    print(
        "Application lock and all-packages/all-extras/all-groups export contain no retired Chroma or ALTK dependencies."
    )


if __name__ == "__main__":
    check_inventory(Path(__file__).resolve().parents[2])
