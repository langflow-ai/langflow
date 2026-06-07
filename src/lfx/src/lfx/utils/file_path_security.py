"""Containment enforcement for tenant-supplied local file paths.

The built-in file-reading components (File, Directory, JSON/CSV-to-Data) accept a filesystem
path from a tenant-controlled input field. Without restriction a tenant can read arbitrary
server files (``/etc/passwd``, the SQLite DB, secrets) or other tenants' uploads.

When ``LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS`` is enabled, resolved local file paths must stay
within the storage data directory (``settings.config_dir``), where uploads live. The check is
a no-op when the setting is disabled (OSS default), so single-tenant deployments keep the
existing "read any local file by absolute path" behavior.
"""

from __future__ import annotations

from pathlib import Path

from lfx.logging import logger
from lfx.services.deps import get_settings_service


class LocalFileAccessError(ValueError):
    """Raised when a resolved path escapes the allowed storage root under restriction."""


def is_local_file_access_restricted() -> bool:
    """Return True if local file access is restricted to the storage directory."""
    try:
        return bool(get_settings_service().settings.restrict_local_file_access)
    except Exception:  # noqa: BLE001 - settings service may be unavailable; fail open to default
        logger.warning(
            "Could not read restrict_local_file_access setting; treating local file restriction "
            "as DISABLED (fail-open to default). Local-file containment is not being enforced."
        )
        return False


def enforce_local_file_access(resolved_path: str | Path) -> Path:
    """Ensure a resolved local path is inside the storage data dir when restriction is on.

    Symlinks are resolved before the containment check so a symlink inside the storage dir
    cannot point outside it.

    Args:
        resolved_path: A filesystem path. It is re-resolved here (``Path.resolve()``) so that
            symlinks are followed before the containment check; the caller need not pre-resolve it.

    Returns:
        The path as a ``Path`` object (unchanged) when allowed.

    Raises:
        LocalFileAccessError: If the restriction is enabled and the path escapes the
            storage data directory.
    """
    path = Path(resolved_path)
    if not is_local_file_access_restricted():
        return path

    data_dir = Path(get_settings_service().settings.config_dir).resolve()
    try:
        candidate = path.resolve()
    except OSError as e:
        msg = f"Could not resolve file path '{resolved_path}': {e}"
        raise LocalFileAccessError(msg) from e

    if not candidate.is_relative_to(data_dir):
        msg = (
            "Access to local file paths outside the storage directory is disabled "
            "(LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS=true). Use an uploaded file instead."
        )
        raise LocalFileAccessError(msg)
    return path
