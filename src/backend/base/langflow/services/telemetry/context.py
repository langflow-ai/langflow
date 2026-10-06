from __future__ import annotations

from contextvars import ContextVar, Token

from lfx.services.telemetry.identity import get_hashed_user_id

_current_telemetry_user_id = ContextVar[str | None]("langflow_telemetry_user_id", default=None)


def set_current_telemetry_user(username: str | None) -> Token[str | None]:
    """Store an opaque IBM custom-realm user ID for the current request task."""
    user_id = get_hashed_user_id(username) if username else None
    return _current_telemetry_user_id.set(user_id)


def get_current_telemetry_user_id() -> str | None:
    """Return the request-local opaque telemetry user ID, if authenticated."""
    return _current_telemetry_user_id.get()


def reset_current_telemetry_user(token: Token[str | None]) -> None:
    """Restore the previous request-local telemetry user ID."""
    _current_telemetry_user_id.reset(token)
