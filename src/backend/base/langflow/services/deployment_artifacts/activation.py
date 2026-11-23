"""Transaction-local extension point for serving-plane activation checks."""

from __future__ import annotations

from contextlib import asynccontextmanager
from contextvars import ContextVar
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

_activation_guard: Callable[..., Awaitable[None]] | None = None
_prepares_memory_bases = False
_extensions_loaded = False
_rollback_cleanups: ContextVar[list | None] = ContextVar("activation_rollback_cleanups", default=None)


def register_activation_rollback_cleanup(cleanup: Callable[[], Awaitable[None]]) -> None:
    """Clean unpublished storage if this replacement attempt does not commit."""
    callbacks = _rollback_cleanups.get()
    if callbacks is None:
        msg = "Activation storage preparation requires a replacement attempt"
        raise RuntimeError(msg)
    callbacks.append(cleanup)


def mark_activation_committed() -> None:
    """Disarm rollback cleanup before any post-commit work or cancellation."""
    callbacks = _rollback_cleanups.get()
    if callbacks is not None:
        callbacks.clear()


@asynccontextmanager
async def activation_attempt(session=None):
    """Keep cleanup local to one request, including transaction retries."""
    from lfx.log.logger import logger

    callbacks: list = []
    token = _rollback_cleanups.set(callbacks)
    try:
        yield
    except BaseException:
        if session is not None:
            # Prove the transaction is no longer pending before a cleanup checks
            # whether its routing row was committed (including an unclear commit).
            try:
                await session.rollback()
            except BaseException:  # noqa: BLE001 - an unclear transaction must retain its storage
                callbacks.clear()
                await logger.awarning("Activation rollback could not be confirmed; retaining storage")
        for cleanup in reversed(callbacks):
            try:
                await cleanup()
            except BaseException:  # noqa: BLE001 - preserve the original refusal or cancellation
                await logger.awarning("Unpublished activation storage cleanup failed")
        raise
    finally:
        _rollback_cleanups.reset(token)


def load_activation_extensions() -> None:
    """Install packaged hooks in API processes and standalone execution workers."""
    global _extensions_loaded  # noqa: PLW0603 - startup registry shared by API and worker entrypoints
    if _extensions_loaded:
        return
    extensions = list(entry_points(group="langflow.variable_activation"))
    if len(extensions) > 1:
        msg = "Only one variable activation extension may be installed"
        raise RuntimeError(msg)
    for extension in extensions:
        extension.load()()
    # A broken extension remains retryable and never silently becomes OSS behavior.
    _extensions_loaded = True


def register_activation_guard(
    guard: Callable[..., Awaitable[None]] | None, *, prepares_memory_bases: bool = False
) -> None:
    """Install a guard before serving requests; None restores the OSS default."""
    global _activation_guard, _prepares_memory_bases  # noqa: PLW0603 - explicit process-wide extension registration
    _activation_guard = guard
    _prepares_memory_bases = guard is not None and prepares_memory_bases


async def guard_project_activation(**context: Any) -> None:
    """Run within replacement's transaction, leaving commit to its caller."""
    load_activation_extensions()
    if context["request"].prepare_memory_bases and not _prepares_memory_bases:
        raise HTTPException(
            status_code=409,
            detail="Empty Memory Base preparation is unavailable on this serving plane",
            headers={"X-Langflow-Error-Code": "memory_base_preparation_unavailable"},
        )
    if _activation_guard is not None:
        await _activation_guard(**context)
    elif context["request"].variables is not None or context["request"].prepare_memory_bases:
        raise HTTPException(
            status_code=409,
            detail="Variable provisioning is unavailable on this serving plane",
            headers={"X-Langflow-Error-Code": "variable_provisioning_unavailable"},
        )
