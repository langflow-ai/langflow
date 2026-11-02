"""Canonical source records validated before durable delivery."""

from __future__ import annotations

import json
from typing import Any

_IDENTITY_LIMITS = {"provider": 32, "resource": 512, "id": 512, "version": 255}


class InvalidSourceItemError(ValueError):
    """A provider returned records outside the canonical source contract."""


def validate_source_items(items: Any, *, provider: str | None = None) -> None:
    """Reject malformed batches before indexing fields or writing database rows.

    Identity limits match TriggerSourceVersion columns. Provider data and any
    optional envelope fields must also survive the ledger's JSON serializer.
    Validation never includes provider payload values in its error messages.
    """
    if not isinstance(items, list | tuple):
        msg = "Source items must be a list or tuple of canonical records."
        raise InvalidSourceItemError(msg)
    for item in items:
        if not isinstance(item, dict):
            msg = "A source item must be a canonical record."
            raise InvalidSourceItemError(msg)
        for field, limit in _IDENTITY_LIMITS.items():
            value = item.get(field)
            if not isinstance(value, str) or not value or len(value) > limit:
                msg = f"A source item has an invalid {field}."
                raise InvalidSourceItemError(msg)
        if provider is not None and item["provider"] != provider:
            msg = "A source item belongs to a different provider."
            raise InvalidSourceItemError(msg)
        if not isinstance(item.get("data"), dict):
            msg = "A source item must contain a data object."
            raise InvalidSourceItemError(msg)
        if "deleted" in item and not isinstance(item["deleted"], bool):
            msg = "A source item has an invalid deletion flag."
            raise InvalidSourceItemError(msg)
        if "session_key" in item and (not isinstance(item["session_key"], str) or not item["session_key"]):
            msg = "A source item has an invalid session key."
            raise InvalidSourceItemError(msg)
        try:
            json.dumps(item, allow_nan=False)
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            msg = "A source item must contain JSON data."
            raise InvalidSourceItemError(msg) from exc
