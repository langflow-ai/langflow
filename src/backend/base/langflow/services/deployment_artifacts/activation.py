"""Transaction-local extension point for serving-plane activation checks."""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

_activation_guard: Callable[..., Awaitable[None]] | None = None
_extensions_loaded = False


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


def register_activation_guard(guard: Callable[..., Awaitable[None]] | None) -> None:
    """Install a guard before serving requests; None restores the OSS default."""
    global _activation_guard  # noqa: PLW0603 - explicit process-wide extension registration
    _activation_guard = guard


async def guard_project_activation(**context: Any) -> None:
    """Run within replacement's transaction, leaving commit to its caller."""
    load_activation_extensions()
    if _activation_guard is not None:
        await _activation_guard(**context)
    elif context["request"].variables is not None:
        raise HTTPException(
            status_code=409,
            detail="Variable provisioning is unavailable on this serving plane",
            headers={"X-Langflow-Error-Code": "variable_provisioning_unavailable"},
        )
