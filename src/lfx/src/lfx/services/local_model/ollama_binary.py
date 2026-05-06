"""Ollama CLI binary detection — cross-platform, no shell, never raises.

Combines `shutil.which` (path lookup) with a guarded `subprocess.run` of
`ollama --version` to corroborate that the binary is the real CLI and not a
stub planted in $PATH. Every external call has an explicit timeout and never
uses shell=True.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_VERSION_TIMEOUT_S = 3.0


def is_ollama_installed() -> bool:
    """Return True iff the Ollama CLI is present AND responds to --version."""
    found = shutil.which("ollama")
    if found is None:
        return False
    try:
        completed = subprocess.run(  # noqa: S603 — list args, no shell, fixed cmd
            [found, "--version"],
            capture_output=True,
            text=True,
            timeout=_VERSION_TIMEOUT_S,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return completed.returncode == 0


def ollama_binary_path() -> Path | None:
    """Return the absolute Path of the Ollama CLI, or None if not found."""
    found = shutil.which("ollama")
    if found is None:
        return None
    return Path(found)
