"""Shared helpers for TOML-based plugin discovery."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from lfx.log.logger import logger


def get_preferred_config_source(
    config_dir: Path,
    *,
    lfx_root_path: tuple[str, ...],
    pyproject_root_path: tuple[str, ...],
) -> tuple[Path, tuple[str, ...]] | None:
    """Return first available config source, preferring ``lfx.toml``."""
    lfx_config = config_dir / "lfx.toml"
    if lfx_config.exists():
        return lfx_config, lfx_root_path

    pyproject_config = config_dir / "pyproject.toml"
    if pyproject_config.exists():
        return pyproject_config, pyproject_root_path

    return None


def load_toml_config(config_path: Path) -> dict[str, Any] | None:
    """Load TOML payload from disk and return it as dict, or ``None`` on failure."""
    try:
        import tomllib as tomli  # Python 3.11+
    except ImportError:
        import tomli  # Python 3.10

    try:
        with config_path.open("rb") as file_handle:
            return tomli.load(file_handle)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to load config from {config_path}: {exc}")
        return None


def get_nested_section(config: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any] | None:
    """Safely resolve nested dictionary section in TOML payloads."""
    node: Any = config
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node if isinstance(node, dict) else None
