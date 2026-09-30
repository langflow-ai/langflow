"""Load the canonical migration table JSON from the in-repo path.

Discovery is deliberately narrow: there is exactly one canonical migration
table file, shipped at :data:`MIGRATION_TABLE_PATH` inside the lfx package.
No environment variable override, no network fetch, no per-deployment table.
A flow saved on machine A and opened on machine B must produce identical
rewrites; the only way to keep that promise is to ship the table with the
runtime.

The loader:

    1. Reads the JSON.
    2. Parses it into a :class:`MigrationTable`.
    3. Caches the parsed instance for the process lifetime (re-loading is
       a CLI / test-only operation; production never bypasses the cache).

Errors come back as :class:`ExtensionError` instances rather than raised
exceptions so callers (deserializer, future events emitter) handle every
failure path uniformly.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from lfx.extension.errors import ExtensionError
from lfx.extension.migration.schema import MigrationTable

# ---------------------------------------------------------------------------
# Canonical path
# ---------------------------------------------------------------------------

# The migration table lives next to this module so it is shipped inside the
# lfx wheel.  Resolving via __file__ is intentional: any other discovery
# mechanism (env vars, cwd lookup) would let two deployments disagree about
# the rewrites for the same flow, which defeats the append-only contract.
_MIGRATION_DIR: Path = Path(__file__).resolve().parent
MIGRATION_TABLE_PATH: Path = _MIGRATION_DIR / "migration_table.json"
"""Canonical on-disk location of the append-only migration table."""


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_cached: MigrationTable | None = None


def _read_json(path: Path) -> tuple[dict | None, ExtensionError | None]:
    """Read and JSON-decode ``path``.  Returns (data, None) or (None, error)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, ExtensionError(
            code="migration-table-missing",
            message=f"Migration table not found at {path}",
            location=str(path),
            hint=(
                "The migration table ships with lfx. If it is missing, "
                "your lfx install is corrupt; reinstall the package."
            ),
        )
    except OSError as exc:
        return None, ExtensionError(
            code="migration-table-unreadable",
            message=f"Could not read migration table at {path}: {exc}",
            location=str(path),
            hint="Check filesystem permissions on the lfx install location.",
        )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, ExtensionError(
            code="migration-table-invalid",
            message=(f"Migration table at {path} is not valid JSON ({exc.msg} at line {exc.lineno})"),
            location=str(path),
            hint=(
                "Run scripts/migrate/check_migration_append_only.py to confirm "
                "the file shape; do not hand-edit production migration tables."
            ),
        )
    if not isinstance(data, dict):
        return None, ExtensionError(
            code="migration-table-invalid",
            message=f"Migration table at {path} top-level value must be a JSON object",
            location=str(path),
            hint="The table is an object with 'schema_version' and 'entries' keys.",
        )
    return data, None


def load_migration_table(
    path: Path | str | None = None,
    *,
    use_cache: bool = True,
) -> tuple[MigrationTable | None, ExtensionError | None]:
    """Load and parse the canonical migration table.

    Args:
        path: Override the canonical path.  Tests use this; production never
            does.  ``None`` means :data:`MIGRATION_TABLE_PATH`.
        use_cache: If True (default) and ``path`` is None, the parsed table
            is cached for the process lifetime.  Reload paths
            (``invalidate_cache``) bust this.

    Returns:
        A ``(table, error)`` pair.  Exactly one of the two is ``None``.
    """
    global _cached  # noqa: PLW0603 - module-level cache, guarded by _lock
    target = Path(path) if path is not None else MIGRATION_TABLE_PATH

    if path is None and use_cache:
        with _lock:
            if _cached is not None:
                return _cached, None

    data, read_error = _read_json(target)
    if read_error is not None or data is None:
        return None, read_error

    try:
        table = MigrationTable.model_validate(data)
    except (ValueError, TypeError) as exc:
        return None, ExtensionError(
            code="migration-table-invalid",
            message=f"Invalid migration table at {target}: {exc}",
            location=str(target),
            hint=(
                "Each entry must populate exactly one of "
                "{bare_class_name, import_path, legacy_slot} and a valid "
                "'ext:<bundle>:<Class>@<slot>' target."
            ),
        )

    if path is None and use_cache:
        with _lock:
            _cached = table

    return table, None


def invalidate_cache() -> None:
    """Drop the cached migration table.

    Tests and the future ``extension reload`` flow call this; production
    request paths never do.
    """
    global _cached  # noqa: PLW0603 - module-level cache, guarded by _lock
    with _lock:
        _cached = None


def empty_table() -> MigrationTable:
    """An in-memory empty table.

    Used by tests and by the deserializer's defensive fallback when the
    on-disk table fails to load: returning an empty table means the
    deserializer reports every legacy reference as unmapped (with a typed
    error) instead of crashing the whole flow load.
    """
    return MigrationTable(schema_version=1, entries=[])
