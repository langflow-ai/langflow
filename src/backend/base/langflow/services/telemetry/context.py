from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

from lfx.services.settings.constants import DEFAULT_SUPERUSER
from lfx.services.telemetry.identity import get_hashed_user_id

if TYPE_CHECKING:
    from collections.abc import Iterator

_current_telemetry_user_id = ContextVar[str | None]("langflow_telemetry_user_id", default=None)


def set_current_telemetry_user(username: str | None) -> Token[str | None]:
    """Store an opaque IBM custom-realm user ID for the current request task."""
    # The shared default account does not identify a person across installations.
    user_id = get_hashed_user_id(username) if username and username != DEFAULT_SUPERUSER else None
    return _current_telemetry_user_id.set(user_id)


def get_current_telemetry_user_id() -> str | None:
    """Return the request-local opaque telemetry user ID, if authenticated."""
    return _current_telemetry_user_id.get()


def clear_current_telemetry_user() -> None:
    """Force installation-level attribution for an unauthenticated caller."""
    _current_telemetry_user_id.set(None)


def reset_current_telemetry_user(token: Token[str | None]) -> None:
    """Restore the previous request-local telemetry user ID."""
    _current_telemetry_user_id.reset(token)


@contextmanager
def telemetry_user_context(user_id: str | None) -> Iterator[None]:
    """Restore a job's already-hashed identity without retaining it on the worker."""
    token = _current_telemetry_user_id.set(user_id)
    try:
        yield
    finally:
        reset_current_telemetry_user(token)
