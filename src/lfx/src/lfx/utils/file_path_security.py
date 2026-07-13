"""Containment enforcement for tenant-supplied local file paths.

The built-in file-reading components (File, Directory, JSON/CSV-to-Data) accept a filesystem
path from a tenant-controlled input field. Without restriction a tenant can read arbitrary
server files (``/etc/passwd``, the SQLite DB, secrets) or other tenants' uploads.

When ``LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS`` is enabled, resolved local file paths must stay
within the storage data directory (``settings.config_dir``), where uploads live. The check is
a no-op when the setting is disabled (OSS default), so single-tenant deployments keep the
existing "read any local file by absolute path" behavior.

Reserved-secret denial: the storage data directory IS ``config_dir``, which also holds the
server-managed secret files as siblings of the per-flow upload subdirectories — the Fernet
master key (``secret_key``), the JWT signing keys (``private_key.pem`` / ``public_key.pem``),
and the SQLite DB when ``save_db_in_config_dir`` is set. The storage-boundary check alone would
permit reading those (e.g. ``<flow>/../secret_key`` resolves back inside ``config_dir``), which
would defeat the control's purpose — reading ``secret_key`` discloses every tenant's stored
credentials. So those exact files are denied explicitly even though they sit inside the boundary.

KNOWN LIMITATION (tracked for follow-up, see ``.claude/security-audit-findings.md``): this does
NOT scope reads per tenant — any ``<config_dir>/<other_flow_id>/<file>`` upload is still in
bounds, so one tenant can read another tenant's uploaded files. Closing that requires
per-user/per-flow scoping at the call sites and is deferred.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from lfx.logging import logger
from lfx.services.deps import get_settings_service


class LocalFileAccessError(ValueError):
    """Raised when a resolved path escapes the allowed storage root under restriction."""


# Server-managed secret/key file names that live directly under config_dir (see auth.py:
# ``secret_key``, ``private_key.pem``, ``public_key.pem``). Matched only at their exact
# config_dir location, never by basename — a tenant upload happens to be named "secret_key"
# inside a flow subdir is a different path and stays readable.
_RESERVED_SECRET_FILENAMES = frozenset({"secret_key", "private_key.pem", "public_key.pem"})


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


def _reserved_secret_paths(data_dir: Path) -> set[Path]:
    """Resolved paths of server-managed secret/key/DB files under the storage dir.

    Reading any of these would compromise the deployment (the Fernet master key decrypts every
    tenant's credentials; the ``*.pem`` keys allow auth-token forgery; the SQLite DB holds all
    rows), so they are denied even though they resolve inside the containment boundary.
    """
    reserved = {(data_dir / name).resolve() for name in _RESERVED_SECRET_FILENAMES}

    # Add the SQLite DB file when it lives under config_dir (``save_db_in_config_dir``).
    # database_url is assembled as ``sqlite:///<absolute path>`` (see settings/base.py); the
    # async ``sqlite+aiosqlite:///`` form is also covered by the ``sqlite`` prefix.
    try:
        db_url = get_settings_service().settings.database_url or ""
    except Exception:  # noqa: BLE001 - settings may be unavailable; nothing to add
        db_url = ""
    if db_url.startswith("sqlite") and ":///" in db_url:
        # Drop any ``?query`` so a custom LANGFLOW_DATABASE_URL still resolves to the file.
        db_path_str = db_url.split(":///", 1)[1].split("?", 1)[0]
        if db_path_str:
            with contextlib.suppress(OSError):
                db_path = Path(db_path_str).resolve()
                reserved.add(db_path)
                # WAL/SHM/journal sidecars hold un-checkpointed DB pages (the same row data),
                # so they must be denied alongside the main DB file.
                for suffix in ("-wal", "-shm", "-journal"):
                    reserved.add(Path(str(db_path) + suffix))
    return reserved


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

    # The storage dir is config_dir, which also holds server-managed secret/key/DB files as
    # siblings of the upload subdirs; deny those explicitly (a traversal like "<flow>/../secret_key"
    # resolves back inside the boundary but must not be readable).
    if candidate in _reserved_secret_paths(data_dir):
        msg = "Access to this server-managed file is not permitted (LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS=true)."
        raise LocalFileAccessError(msg)
    return candidate
