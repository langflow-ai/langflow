"""SVC-01 starter-projects hash gate helpers.

Computes a content hash over the starter-project JSON files plus the installed
``lfx`` package version, and persists it as plaintext under
``${LANGFLOW_CONFIG_DIR}/starter_projects.hash``. ``main.py`` uses the hash to
short-circuit the full starter-project re-sync on restarts where nothing
changed.

Failure modes (D-04): missing, unreadable, or corrupt hash files all fall
through to a full re-sync. ``LANGFLOW_FORCE_STARTER_RESYNC=1`` bypasses the
comparison. Write failures (read-only root filesystem, e.g. container
deployments) log at debug level and never raise -- mirroring the
``update_project_file`` pattern at ``setup.py:690-701``.
"""

from __future__ import annotations

import hashlib
import os
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

import aiofiles
from lfx.log.logger import logger

if TYPE_CHECKING:
    from pathlib import Path

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
    fallback fires in a fresh environment -- acceptable per D-01.
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
    to a full re-sync (D-04).
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

    Ensures the parent directory exists (``mkdir(parents=True, exist_ok=True)``
    on the parent). Swallows ``OSError`` (Pattern E) so that a read-only
    filesystem -- common in containerized deployments with
    ``readOnlyRootFilesystem: true`` -- does not crash lifespan startup; the
    hash gate simply falls through to a full re-sync on every restart in that
    environment.
    """
    content = f"{sha_hex}\n# version: {version_string}\n"
    try:
        hash_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(str(hash_path), "w", encoding="utf-8") as f:
            await f.write(content)
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
