"""Keep connection failure evidence separate from ordinary trigger edits."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.services.database.models.trigger.model import Trigger

_RECOVERY_KEY = "_connection_recovery"


def record_connection_failure(row: Trigger, *, failed_at: datetime, consent_required: bool = False) -> None:
    """Preserve provider cursors while recording the latest failed authorization."""
    row.provider_state = {
        **(row.provider_state or {}),
        _RECOVERY_KEY: {"failed_at": failed_at.isoformat(), "consent_required": consent_required},
    }


def connection_failure(row: Trigger) -> tuple[datetime | None, bool]:
    """Read stable evidence, falling back conservatively for older trigger rows."""
    metadata = (row.provider_state or {}).get(_RECOVERY_KEY)
    if metadata is None:
        failed_at = as_utc(row.updated_at)
        # Legacy database timestamps can omit subseconds. Do not treat an
        # unchanged token from that same second as proof of reconnection.
        if failed_at is not None and failed_at.microsecond == 0:
            failed_at = failed_at.replace(microsecond=999999)
        return failed_at, False
    if not isinstance(metadata, dict):
        return None, False
    try:
        failed_at = datetime.fromisoformat(metadata["failed_at"])
    except (KeyError, TypeError, ValueError):
        return None, False
    return as_utc(failed_at), metadata.get("consent_required") is True


def as_utc(value: datetime | None) -> datetime | None:
    """Normalize SQLite's naive timestamps without assuming a missing timestamp."""
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
