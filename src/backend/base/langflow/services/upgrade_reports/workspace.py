"""Remove upgrade check workspaces once no server or checker owns them."""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import anyio
from lfx.log.logger import logger

if os.name == "posix":
    import fcntl

if TYPE_CHECKING:
    from collections.abc import Iterator

RUN_FOLDER_PREFIX = "langflow-upgrade-check-run-"
_LOCK_MARKER = ".managed"
_SWEEP_INTERVAL_SECONDS = 60


@contextlib.contextmanager
def _open_folder_lock(folder: Path) -> Iterator[int]:
    fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield fd
    finally:
        # The checker may still hold the same lock after the server exits.
        os.close(fd)


@contextlib.contextmanager
def hold_run_folder(folder: Path) -> Iterator[int | None]:
    """Hold the directory lock and make the folder eligible for later cleanup."""
    if os.name != "posix":
        yield None
        return

    with _open_folder_lock(folder) as fd:
        (folder / _LOCK_MARKER).touch()
        yield fd


def _sweep_run_folders(root: Path) -> None:
    for folder in root.glob(f"{RUN_FOLDER_PREFIX}*"):
        try:
            # Earlier versions did not lock their folders. Leave them alone during a rolling update.
            if folder.lstat().st_uid != os.geteuid() or folder.is_symlink() or not (folder / _LOCK_MARKER).is_file():
                continue
            with _open_folder_lock(folder):
                shutil.rmtree(folder)
        except (FileNotFoundError, BlockingIOError, PermissionError):
            continue
        except OSError as exc:
            logger.warning(f"Could not remove an abandoned upgrade check folder: {exc}")


async def sweep_run_folders_periodically() -> None:
    """Sweep at startup and retry later if an orphaned checker still has its lock."""
    if os.name != "posix":
        return

    while True:
        try:
            await anyio.to_thread.run_sync(_sweep_run_folders, Path(tempfile.gettempdir()))
        except OSError as exc:
            await logger.awarning(f"Could not scan for abandoned upgrade check folders: {exc}")
        await asyncio.sleep(_SWEEP_INTERVAL_SECONDS)
