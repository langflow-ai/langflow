"""Containment enforcement for tenant-supplied local file paths.

The built-in file-reading components accept filesystem paths from tenant-controlled input.
When ``LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS`` is enabled, those paths must resolve within the
authenticated user's or executing flow's storage directory under ``settings.config_dir``.
The check is disabled by default to preserve existing single-tenant behavior.

Server-managed key files and the configured SQLite database (including its sidecars) are
denied explicitly. They may live under ``config_dir`` but must never be exposed to tenants.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING

from lfx.logging import logger
from lfx.services.deps import get_settings_service

if TYPE_CHECKING:
    from collections.abc import Iterable


class LocalFileAccessError(ValueError):
    """Raised when a resolved path escapes the allowed storage root under restriction."""


_RESERVED_SECRET_FILENAMES = frozenset({"secret_key", "private_key.pem", "public_key.pem"})


def is_local_file_access_restricted() -> bool:
    """Return whether local-file access is restricted to tenant storage."""
    try:
        return bool(get_settings_service().settings.restrict_local_file_access)
    except Exception:  # noqa: BLE001 - settings may be unavailable; preserve the disabled default
        logger.warning(
            "Could not read restrict_local_file_access setting; treating local file restriction "
            "as DISABLED (fail-open to default). Local-file containment is not being enforced."
        )
        return False


def _reserved_secret_paths(data_dir: Path) -> set[Path]:
    """Return resolved paths of server-managed key and database files."""
    reserved = {(data_dir / name).resolve() for name in _RESERVED_SECRET_FILENAMES}

    try:
        db_url = get_settings_service().settings.database_url or ""
    except Exception:  # noqa: BLE001 - settings may be unavailable; nothing to add
        db_url = ""
    if db_url.startswith("sqlite") and ":///" in db_url:
        db_path_str = db_url.split(":///", 1)[1].split("?", 1)[0]
        if db_path_str:
            with contextlib.suppress(OSError):
                db_path = Path(db_path_str).resolve()
                reserved.add(db_path)
                for suffix in ("-wal", "-shm", "-journal"):
                    reserved.add(Path(str(db_path) + suffix))
    return reserved


def component_file_access_scopes(component: object) -> tuple[str, ...]:
    """Return the component's authenticated user and flow storage scopes, when available."""
    graph = getattr(getattr(component, "_vertex", None), "graph", None)
    candidates = (
        getattr(component, "_user_id", None) or getattr(graph, "user_id", None),
        getattr(graph, "flow_id", None),
    )
    scopes: list[str] = []
    for candidate in candidates:
        if candidate is not None:
            scope = str(candidate).strip()
            if scope and scope not in scopes:
                scopes.append(scope)
    return tuple(scopes)


def _scope_roots(data_dir: Path, scope_ids: Iterable[object] | None) -> tuple[Path, ...]:
    """Build validated storage roots for the current authenticated user and flow."""
    if isinstance(scope_ids, (str, bytes)):
        scope_ids = (scope_ids,)
    roots: list[Path] = []
    for raw_scope in scope_ids or ():
        scope = str(raw_scope).strip()
        if not scope or scope in {".", ".."} or any(char in scope for char in ("/", "\\", "\x00")):
            msg = "Invalid local-file access scope."
            raise LocalFileAccessError(msg)
        root = (data_dir / scope).resolve()
        if not root.is_relative_to(data_dir):
            msg = "Invalid local-file access scope."
            raise LocalFileAccessError(msg)
        if root not in roots:
            roots.append(root)

    if not roots:
        msg = (
            "Local-file access requires an authenticated user or flow scope "
            "when LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS=true."
        )
        raise LocalFileAccessError(msg)
    return tuple(roots)


def enforce_local_file_access(
    resolved_path: str | Path,
    *,
    scope_ids: Iterable[object] | None = None,
) -> Path:
    """Resolve and confine a local path to the current user's or flow's storage scope."""
    path = Path(resolved_path)
    if not is_local_file_access_restricted():
        return path

    data_dir = Path(get_settings_service().settings.config_dir).resolve()
    allowed_roots = _scope_roots(data_dir, scope_ids)
    try:
        candidate = path.resolve()
    except OSError as e:
        msg = f"Could not resolve file path '{resolved_path}': {e}"
        raise LocalFileAccessError(msg) from e

    if not any(candidate == root or candidate.is_relative_to(root) for root in allowed_roots):
        msg = (
            "Access to local file paths outside the authenticated user's storage scope is disabled "
            "(LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS=true). Use an uploaded file instead."
        )
        raise LocalFileAccessError(msg)

    if candidate in _reserved_secret_paths(data_dir):
        msg = "Access to this server-managed file is not permitted (LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS=true)."
        raise LocalFileAccessError(msg)
    return candidate
