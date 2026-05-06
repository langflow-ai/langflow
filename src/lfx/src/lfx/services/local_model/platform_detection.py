"""Platform detection — answers "what platform am I on?" cross-OS.

Pure helper layer: only filesystem stat and environment variable reads.
No subprocess, no network — those belong in sibling modules.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Literal

PlatformName = Literal["windows", "macos", "linux", "unknown"]

_DOCKER_ENV_FILE = Path("/.dockerenv")


def system_name() -> PlatformName:
    """Return the canonical lowercase OS name, or 'unknown' for uncommon platforms."""
    raw = platform.system()
    if raw == "Windows":
        return "windows"
    if raw == "Darwin":
        return "macos"
    if raw == "Linux":
        return "linux"
    return "unknown"


def is_docker() -> bool:
    """Return True if the current process appears to be running inside a container.

    Multiple signals are checked because no single one is universal:
      - /.dockerenv : created by the Docker daemon (Moby's recommended marker)
      - KUBERNETES_SERVICE_HOST : injected by the kubelet in K8s pods
    """
    if _DOCKER_ENV_FILE.exists():
        return True
    return bool(os.environ.get("KUBERNETES_SERVICE_HOST"))
