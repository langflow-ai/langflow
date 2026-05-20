"""Isolation configuration for the FileSystem tool.

Single env var: ``LANGFLOW_FS_TOOL_BASE_DIR`` controls where on disk the tool
sandboxes everything. The pepper file used to hash user_ids in isolated mode
lives at ``<base>/.fs_pepper`` — derived, never separately configured.

The decision between **shared** and **isolated** layout is made by the
component at call time based on ``AUTO_LOGIN``; this module knows nothing
about that policy. It only resolves where things live on disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

BASE_DIR_ENV = "LANGFLOW_FS_TOOL_BASE_DIR"

DEFAULT_BASE_DIR_NAME = "fs_sandbox"
DEFAULT_PEPPER_FILENAME = ".fs_pepper"


@dataclass(frozen=True)
class IsolationConfig:
    """Resolved on-disk layout for one FileSystem tool call — immutable."""

    base_dir: Path
    pepper_path: Path


def load_isolation_config(
    *,
    env: Mapping[str, str],
    default_config_dir: Path,
) -> IsolationConfig:
    """Build an immutable IsolationConfig from environment variables.

    Why ``env`` is injected: lets tests pass a tiny dict instead of patching
    ``os.environ`` (which leaks across xdist workers and is order-dependent).
    """
    base_dir_raw = env.get(BASE_DIR_ENV)
    if not base_dir_raw or not base_dir_raw.strip():
        base_dir_raw = str(default_config_dir / DEFAULT_BASE_DIR_NAME)

    base_dir = Path(base_dir_raw).resolve()
    pepper_path = (base_dir / DEFAULT_PEPPER_FILENAME).resolve()

    return IsolationConfig(base_dir=base_dir, pepper_path=pepper_path)
