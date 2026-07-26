"""Filesystem locations for performance-suite runtime artifacts.

Reports, provision state, and generated corpora are written **outside** the
repository by default (under the user cache). Override with ``PERF_DATA_DIR``.
"""

from __future__ import annotations

import os
from pathlib import Path

_SUITE_CACHE_NAME = "langflow-perf"


def perf_data_root() -> Path:
    """Return the root directory for suite-generated artifacts.

    Resolution order:
    1. ``PERF_DATA_DIR`` (explicit override)
    2. ``$XDG_CACHE_HOME/langflow-perf`` when ``XDG_CACHE_HOME`` is set
    3. ``~/.cache/langflow-perf``
    """
    override = os.environ.get("PERF_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return (Path(xdg).expanduser() / _SUITE_CACHE_NAME).resolve()
    return (Path.home() / ".cache" / _SUITE_CACHE_NAME).resolve()


def reports_dir() -> Path:
    return perf_data_root() / "reports"


def state_dir() -> Path:
    return perf_data_root() / "state"


def corpus_dir(env_id: str) -> Path:
    safe = env_id.replace("/", "_").replace("..", "_")
    return perf_data_root() / "corpus" / safe


def state_path_for(env_id: str, *, data_root: Path | None = None) -> Path:
    safe = env_id.replace("/", "_").replace("..", "_")
    root = data_root if data_root is not None else perf_data_root()
    return root / "state" / f"{safe}.json"


def ensure_data_dirs() -> Path:
    """Create the standard artifact directories and return the data root."""
    root = perf_data_root()
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "state").mkdir(parents=True, exist_ok=True)
    (root / "corpus").mkdir(parents=True, exist_ok=True)
    return root
