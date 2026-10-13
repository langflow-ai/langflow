"""Bounded migration-state reads and cancellation-safe owned operations."""

from __future__ import annotations

import asyncio
import os
import stat
from typing import TYPE_CHECKING, ParamSpec, TypeVar

from langflow.services.knowledge_base_storage.maintenance import MaintenanceRequiredError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_P = ParamSpec("_P")
_Result = TypeVar("_Result")


async def drain_task(task: asyncio.Task[_Result]) -> _Result:
    """Finish an owned operation before propagating cancellation."""
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            if not cancelled:
                raise
    if cancelled:
        task.exception()
        raise asyncio.CancelledError
    return task.result()


async def run_worker(function: Callable[_P, _Result], *args: _P.args, **kwargs: _P.kwargs) -> _Result:
    """Keep the migration fence until a disk worker has finished."""
    return await drain_task(asyncio.create_task(asyncio.to_thread(function, *args, **kwargs)))


def read_regular_file(path: Path, *, limit: int) -> bytes:
    """Read bounded migration state without following a final symlink or blocking on a FIFO."""
    if not path.is_absolute() or path.is_symlink():
        msg = "Migration state must be an absolute regular file"
        raise MaintenanceRequiredError(msg)
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise ValueError
            result = stream.read(limit + 1)
            if len(result) > limit:
                raise ValueError
            return result
    except (OSError, ValueError) as exc:
        msg = "Migration state is missing, invalid or exceeds its size limit"
        raise MaintenanceRequiredError(msg) from exc
