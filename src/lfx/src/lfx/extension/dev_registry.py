"""Local dev-extension registry for ``lfx extension dev``.

When an author types ``lfx extension dev <path>``, we don't ship the
Extension via pip; instead we record the absolute path in a small JSON
state file, then hand off to ``langflow run``.  At server startup, the
loader reads this state file and registers each surviving directory at
the ``official`` slot via :func:`lfx.extension.loader.load_extension`.
Paths that have moved or been deleted surface as
``local-extension-missing`` warnings rather than aborting startup.

State file shape (kebab-case path under the langflow user-cache dir)::

    <user_cache_dir>/extensions/dev_extensions.json

::

    {
      "version": 1,
      "extensions": [
        {"path": "/abs/path/to/my-ext", "registered_at": "2026-05-04T12:34:56Z"}
      ]
    }

Concurrency: the state file is rewritten atomically (tempfile + rename).
We do not take a long-lived lock; the file is read-mostly and the only
writer is the ``extension dev`` CLI invoked synchronously by a developer.

Scope notes:

    - This module only writes / reads / lists the state file; the actual
      registration is consumed by Langflow's startup hook.  The runtime
      "remove" path (``extension dev --unregister``) is a deliberate
      non-goal for v0; authors clean up by deleting the state file or
      the directory.
    - The reload pipeline reuses :func:`load_dev_extensions` to refresh
      the @official slot mid-run; the reload UX itself ships there.
    - Installed-package discovery keeps its own primitives and is
      orthogonal -- both flows produce ``LoadResult`` lists that
      Langflow startup merges in the same step.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from lfx.extension.errors import ExtensionError
from lfx.extension.loader import load_extension
from lfx.extension.loader._types import LoadResult

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State-file location + shape
# ---------------------------------------------------------------------------

DEV_REGISTRY_VERSION: int = 1
"""Schema version of the dev_extensions.json file.  Bump when an
incompatible change to the on-disk layout is required."""

_STATE_FILE_NAME: str = "dev_extensions.json"


def _default_state_dir() -> Path:
    """Return the directory in which the dev registry lives.

    Resolution order:
        1. ``LANGFLOW_DEV_EXTENSIONS_DIR`` (test seam + override).
        2. ``LANGFLOW_CONFIG_DIR/extensions`` if ``LANGFLOW_CONFIG_DIR`` is set.
        3. ``platformdirs.user_cache_dir("langflow", "langflow")/extensions``.

    Created lazily on first write.
    """
    override = os.environ.get("LANGFLOW_DEV_EXTENSIONS_DIR")
    if override:
        return Path(override)

    config_dir = os.environ.get("LANGFLOW_CONFIG_DIR")
    if config_dir:
        return Path(config_dir) / "extensions"

    from platformdirs import user_cache_dir

    return Path(user_cache_dir("langflow", "langflow")) / "extensions"


def state_file_path(state_dir: Path | None = None) -> Path:
    """Return the absolute path to the dev_extensions.json state file."""
    base = state_dir if state_dir is not None else _default_state_dir()
    return base / _STATE_FILE_NAME


# ---------------------------------------------------------------------------
# Entry shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DevExtensionEntry:
    """One row of the dev registry.

    Frozen so callers (the loader, the CLI, tests) can place these in
    sets / dicts and pass them through layers without mutation surprises.
    """

    path: Path
    registered_at: str
    """ISO-8601 UTC timestamp ('YYYY-MM-DDTHH:MM:SSZ') of when this entry
    was added.  Surfaced for ``extension list`` so authors can audit
    what's registered."""


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Read / write helpers
# ---------------------------------------------------------------------------


def _read_state(state_path: Path) -> list[DevExtensionEntry]:
    """Parse the state file.  Missing file yields an empty list; corrupt state logs a warning.

    Three failure modes are distinguished:

    * **File absent** -- legitimate empty registry, return ``[]`` silently.
    * **File present but unreadable** (permission error etc.) -- log a
      WARNING so the operator does not silently lose every registered dev
      extension on the next ``langflow run`` with no diagnostic.  A
      ``PermissionError`` does NOT self-heal; treating it as an empty
      registry was burning real debug cycles in practice.
    * **File present but corrupt JSON / wrong shape** -- log a WARNING
      with the failure detail and return ``[]`` so the dev loop keeps
      working (the ``extension dev`` CLI rewrites the file on the next
      invocation, so a hand-edit typo self-heals as soon as the author
      re-registers).
    """
    if not state_path.is_file():
        return []
    try:
        raw = state_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning(
            "dev_registry: state file %s exists but is unreadable (%s); "
            "treating as empty registry. Registered dev extensions will not load.",
            state_path,
            exc,
        )
        return []
    try:
        data = json.loads(raw)
    except ValueError as exc:
        logger.warning(
            "dev_registry: state file %s contains malformed JSON (%s); "
            "treating as empty registry. Re-run `lfx extension dev <path>` "
            "to repair the registry.",
            state_path,
            exc,
        )
        return []
    if not isinstance(data, dict):
        logger.warning(
            "dev_registry: state file %s top-level value is not an object; treating as empty registry.",
            state_path,
        )
        return []
    extensions = data.get("extensions")
    if not isinstance(extensions, list):
        return []
    entries: list[DevExtensionEntry] = []
    for item in extensions:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if not isinstance(path, str) or not path:
            continue
        registered_at = item.get("registered_at")
        if not isinstance(registered_at, str):
            registered_at = ""
        entries.append(DevExtensionEntry(path=Path(path), registered_at=registered_at))
    return entries


def _write_state(state_path: Path, entries: Iterable[DevExtensionEntry]) -> None:
    """Atomically rewrite the state file with ``entries``.

    Uses tempfile + ``os.replace`` so a crashing writer never leaves a
    half-written file behind; readers always see either the previous
    consistent state or the new one.

    The state file is created with mode 0600 (owner read/write only).
    The file feeds arbitrary ``path`` strings straight into the loader's
    code-loading path at startup, so any process able to write
    ``dev_extensions.json`` gets code loaded at the next ``langflow run``;
    restricting permissions to the owning developer is the trust boundary
    we can enforce at the filesystem level.
    """
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": DEV_REGISTRY_VERSION,
        "extensions": [
            {
                "path": str(entry.path),
                "registered_at": entry.registered_at,
            }
            for entry in entries
        ],
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    fd, tmp_name = tempfile.mkstemp(
        prefix=".dev_extensions.",
        suffix=".tmp",
        dir=str(state_path.parent),
    )
    try:
        try:
            fh = os.fdopen(fd, "w", encoding="utf-8")
        except BaseException:
            os.close(fd)
            raise
        with fh:
            fh.write(serialized)
        # 0600: owner read/write only.  Path.chmod is a no-op on Windows but
        # POSIX systems get the tightened permission before the rename so
        # there is no observable mode-0644 window.  Filesystems without
        # mode-bit support (some Windows FATs) silently ignore chmod; the
        # data is still correct so do not abort the rename.
        with contextlib.suppress(OSError):
            Path(tmp_name).chmod(stat.S_IRUSR | stat.S_IWUSR)
        Path(tmp_name).replace(state_path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# Public API: register / list
# ---------------------------------------------------------------------------


def list_dev_extensions(*, state_dir: Path | None = None) -> list[DevExtensionEntry]:
    """Return all entries in the dev registry, in insertion order."""
    return _read_state(state_file_path(state_dir))


def register_dev_extension(path: Path | str, *, state_dir: Path | None = None) -> DevExtensionEntry:
    """Add ``path`` (resolved to absolute) to the dev registry.

    Idempotent: re-registering an existing path refreshes its
    ``registered_at`` timestamp but does not duplicate the entry.

    Raises:
        FileNotFoundError: ``path`` does not exist or is not a directory.

    Returns:
        The :class:`DevExtensionEntry` just inserted (or refreshed).
    """
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_dir():
        msg = f"Extension path does not exist or is not a directory: {resolved}"
        raise FileNotFoundError(msg)

    state_path = state_file_path(state_dir)
    entries = _read_state(state_path)
    new_entry = DevExtensionEntry(path=resolved, registered_at=_utcnow_iso())
    # Drop any prior entry pointing at the same resolved path.
    entries = [e for e in entries if e.path != resolved]
    entries.append(new_entry)
    _write_state(state_path, entries)
    return new_entry


def unregister_dev_extension(path: Path | str, *, state_dir: Path | None = None) -> bool:
    """Remove ``path`` from the dev registry.

    Returns ``True`` if an entry was removed, ``False`` if the path was
    not in the registry.  Provided for tests and tooling; the ``extension
    dev --unregister`` CLI verb itself is deferred (out of scope for v0).
    """
    resolved = Path(path).expanduser().resolve()
    state_path = state_file_path(state_dir)
    entries = _read_state(state_path)
    new_entries = [e for e in entries if e.path != resolved]
    if len(new_entries) == len(entries):
        return False
    _write_state(state_path, new_entries)
    return True


# ---------------------------------------------------------------------------
# Discovery: load every registered extension at startup
# ---------------------------------------------------------------------------


def load_dev_extensions(*, state_dir: Path | None = None) -> list[LoadResult]:
    """Load every registered dev Extension.

    Reads the state file, calls :func:`load_extension` for each entry
    that still resolves to a directory, and returns the resulting list of
    :class:`LoadResult`s in registration order.

    Missing entries (the directory was renamed, deleted, or moved) are
    surfaced as :class:`LoadResult` instances containing a single
    ``local-extension-missing`` warning so the events pipeline can
    report them without aborting startup.  The author sees a typed
    warning rather than a stack trace.

    The dev registry is never silently mutated by this function: stale
    entries stay in the file so the author can fix the underlying path
    (move the directory back, fix the permissions) and see the extension
    reappear without re-registering.
    """
    results: list[LoadResult] = []
    for entry in list_dev_extensions(state_dir=state_dir):
        if not entry.path.is_dir():
            result = LoadResult(slot="official", source_path=entry.path)
            result.warnings.append(
                ExtensionError(
                    code="local-extension-missing",
                    message=(f"Registered dev extension at {entry.path} is no longer a directory."),
                    location=str(entry.path),
                    content=str(entry.path),
                    hint=(
                        "Restore the directory or run `lfx extension dev <path>` "
                        "again to refresh the registry once the directory is back."
                    ),
                )
            )
            results.append(result)
            continue
        results.append(load_extension(entry.path))
    return results


def dev_extension_component_paths(*, state_dir: Path | None = None) -> tuple[list[Path], list[ExtensionError]]:
    """Return ``(bundle_paths, errors)`` for the registered dev extensions.

    Surface contract:
        - ``bundle_paths`` includes only entries whose manifest parses
          and whose bundle directory exists.  Each path is the resolved
          absolute path to the bundle directory (e.g. ``my-ext/components``).
        - ``errors`` carries one :class:`ExtensionError` per entry that
          could not be loaded (missing path, malformed manifest, etc.).
          Callers should log these but should NOT abort startup.

    Kept for callers that only need bundle directories (tools that walk
    paths, IDE integrations).  The Langflow startup path itself uses
    :func:`load_dev_extensions` so dev extensions land in the
    BundleRegistry alongside installed extensions and become reloadable.
    """
    bundle_paths: list[Path] = []
    errors: list[ExtensionError] = []
    for result in load_dev_extensions(state_dir=state_dir):
        # Forward EVERY warning, not just local-extension-missing: the
        # caller (Langflow's lifespan hook) is the only thing that turns
        # these into a log line, so dropping any of them silences a real
        # signal (e.g. duplicate-component-name, duplicate-inline-bundle).
        errors.extend(result.warnings)
        if result.errors:
            errors.extend(result.errors)
            continue
        if not result.components:
            continue

        if result.source_path is None:
            # Defensive: the loader currently always sets ``source_path``,
            # but a future caller that builds LoadResult by hand could
            # produce a non-empty components list without one.  Surface a
            # typed warning rather than dropping the extension silently.
            errors.append(
                ExtensionError(
                    code="local-extension-missing",
                    message=(
                        "Dev extension produced components but no source_path; the loader "
                        "contract was violated.  Skipping until the loader is fixed."
                    ),
                    location="<unknown>",
                    hint=("File a bug against lfx.extension.loader: LoadResult had components but no source_path."),
                )
            )
            continue

        # Pick the bundle root: the shallowest path *under the extension
        # root* that any registered component lives in.  We measure depth
        # against ``source_path`` (the extension root) rather than absolute
        # part count so siblings at different absolute depths still resolve
        # correctly.
        source_root = result.source_path
        bundle_dirs = {component.file_path.parent for component in result.components}
        top = min(bundle_dirs, key=lambda p: len(p.relative_to(source_root).parts))
        bundle_paths.append(top)
    return bundle_paths, errors
