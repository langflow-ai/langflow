from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

from lfx.services.telemetry.identity import get_installation_user_id, is_installation_user_id

if TYPE_CHECKING:
    from collections.abc import Iterator
    from uuid import UUID

_current_telemetry_user_id = ContextVar[str | None]("langflow_telemetry_user_id", default=None)


def set_current_telemetry_user(user_id: UUID | None, installation_id: str | None = None) -> Token[str | None]:
    """Store an installation-scoped pseudonym of an authenticated database UUID."""
    opaque_id = get_installation_user_id(user_id, installation_id) if user_id and installation_id else None
    return _current_telemetry_user_id.set(opaque_id)


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
    token = _current_telemetry_user_id.set(user_id if is_installation_user_id(user_id) else None)
    try:
        yield
    finally:
        reset_current_telemetry_user(token)
