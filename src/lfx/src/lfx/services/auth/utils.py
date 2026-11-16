"""Context shared by native and delegated synchronous authentication checks."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterator

_sync_auth_validation: ContextVar[bool] = ContextVar("sync_auth_validation", default=False)


def is_sync_auth_validation() -> bool:
    return _sync_auth_validation.get()


@contextmanager
def sync_auth_validation() -> Iterator[None]:
    token = _sync_auth_validation.set(True)
    try:
        yield
    finally:
        _sync_auth_validation.reset(token)


def run_sync_auth_validation(validate: Callable[[], Awaitable[None]]) -> None:
    from lfx.services.deps import get_auth_service
    from lfx.utils.async_helpers import run_until_complete

    auth = get_auth_service()
    if auth is None:
        run_until_complete(validate())
    else:
        auth.run_sync_validation(validate)
