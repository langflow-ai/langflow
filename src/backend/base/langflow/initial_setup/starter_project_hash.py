"""starter-projects hash gate helpers.

Computes a content hash over the starter-project JSON files plus the installed
``lfx`` package version, and persists it as plaintext under
``${LANGFLOW_CONFIG_DIR}/starter_projects.hash``. ``preload.py`` uses the hash
to short-circuit the full starter-project re-sync on restarts where nothing
changed.

Failure modes: missing, unreadable, or corrupt hash files all fall
through to a full re-sync. ``LANGFLOW_FORCE_STARTER_RESYNC=1`` bypasses the
comparison. Write failures (read-only root filesystem, e.g. container
deployments) log at debug level and never raise -- mirroring the
``update_project_file`` pattern at ``setup.py:690-701``.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles
from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import anyio

HASH_FILENAME = "starter_projects.hash"
_HEX_LEN = 64


async def compute_starter_projects_hash(starter_folder: anyio.Path) -> str:
    """Return a SHA256 hex digest over the starter folder contents + ``lfx`` version.

    The digest updates with ``filename || NUL || file_bytes || NUL`` for each
    ``*.json`` file in ``starter_folder`` sorted by filename, followed by the
    installed ``lfx`` package version string. Sorting is load-bearing: glob
    order is not stable across filesystems.

    If ``importlib.metadata.version("lfx")`` raises ``PackageNotFoundError``
    (source-only checkout without ``pip install -e .``), the sentinel
    ``"unknown"`` is substituted (Pattern F / Pitfall 5). The hash remains
    stable within such an environment but will invalidate whenever the
    fallback fires in a fresh environment -- acceptable .
    """
    try:
        pkg_version = version("lfx")
    except PackageNotFoundError:
        pkg_version = "unknown"
    hasher = hashlib.sha256()
    paths = sorted(
        [p async for p in starter_folder.glob("*.json")],
        key=lambda p: p.name,
    )
    for path in paths:
        hasher.update(path.name.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(await path.read_bytes())
        hasher.update(b"\x00")
    hasher.update(pkg_version.encode("utf-8"))
    return hasher.hexdigest()


async def read_hash_file_safe(hash_path: Path) -> str | None:
    """Return the stored SHA hex string, or ``None`` on any failure.

    Skips comment lines (starting with ``#``) and returns the first line that
    is exactly 64 lowercase hex characters. Returns ``None`` for:

    - Missing file (``FileNotFoundError``)
    - Unreadable file (``OSError`` / ``PermissionError``)
    - Empty content
    - Corrupt content (first non-comment line is not 64 hex chars)

    The caller is expected to treat ``None`` as a cache miss and fall through
    to a full re-sync.
    """
    try:
        async with aiofiles.open(str(hash_path), encoding="utf-8") as f:
            content = await f.read()
    except (OSError, FileNotFoundError):
        return None
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if len(line) == _HEX_LEN and all(c in "0123456789abcdef" for c in line):
            return line
        return None
    return None


async def write_hash_file_safe(hash_path: Path, sha_hex: str, version_string: str) -> None:
    """Write ``sha_hex`` + a ``# version:`` comment line to ``hash_path``.

    Atomic write: a uniquely-named temp file is created in the SAME directory
    as ``hash_path`` and then renamed via ``os.replace`` so concurrent writers
    cannot tear the target file and so a crash mid-write leaves either the old
    value or the new value, never a truncated one. The unique tempfile name
    (``tempfile.mkstemp``) is required because the hash gate runs without a
    FileLock at every preload call site.

    Ensures the parent directory exists. Swallows ``OSError`` (Pattern E) so
    that a read-only filesystem -- common in containerized deployments with
    ``readOnlyRootFilesystem: true`` -- does not crash lifespan startup; the
    hash gate simply falls through to a full re-sync on every restart in that
    environment.
    """
    content = f"{sha_hex}\n# version: {version_string}\n"
    try:
        hash_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_name = tempfile.mkstemp(
            prefix=hash_path.name + ".",
            suffix=".tmp",
            dir=hash_path.parent,
        )
        tmp_path = Path(tmp_name)
        try:
            async with aiofiles.open(tmp_fd, "w", encoding="utf-8", closefd=True) as f:
                await f.write(content)
                await f.flush()
            tmp_path.replace(hash_path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
    except OSError as e:
        await logger.adebug(
            f"Could not write starter-projects hash file (read-only filesystem): {e}. "
            "Hash gate will fall through to full re-sync on each restart."
        )


def is_force_resync_requested() -> bool:
    """Return ``True`` if ``LANGFLOW_FORCE_STARTER_RESYNC`` is set to 1/true/yes.

    Comparison is case-insensitive and whitespace-stripped. Any other value
    (empty string, unset, "no", "0") returns ``False`` so the hash comparison
    path runs normally.
    """
    return os.getenv("LANGFLOW_FORCE_STARTER_RESYNC", "").strip().lower() in ("1", "true", "yes")


async def run_starter_projects_hash_gate(
    *,
    starter_folder: anyio.Path,
    hash_path: Path,
    sync_fn: Callable[[], Awaitable[Any]],
) -> bool:
    """Execute the hash-gated starter-project sync.

    This helper encapsulates the hash compare / sync / write sequence so both
    ``main.py`` (inside its ``FileLock``) and the parity tests invoke
    the exact same code path. ``sync_fn`` is a zero-arg coroutine factory the
    caller uses to pass in ``create_or_update_starter_projects(all_types_dict)``
    with ``all_types_dict`` already bound.

    Returns ``True`` when the full re-sync ran (cache miss or force-resync),
    ``False`` when the hash matched and the sync was skipped.

    The caller is responsible for wrapping this in its own ``FileLock`` /
    error-handling context (TOCTOU safety per Pitfall 2). The gate itself
    does not manage locking.
    """
    expected = await compute_starter_projects_hash(starter_folder)
    actual = await read_hash_file_safe(hash_path)
    if is_force_resync_requested() or actual != expected:
        await sync_fn()
        try:
            pkg_v = version("lfx")
        except PackageNotFoundError:
            pkg_v = "unknown"
        await write_hash_file_safe(hash_path, expected, pkg_v)
        return True
    await logger.adebug("Starter projects hash matches; skipped re-sync")
    return False
