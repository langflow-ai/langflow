"""Privacy rules applied when serializing outbound product telemetry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import BaseModel


def get_safe_payload_properties(payload: BaseModel) -> dict[str, Any]:
    """Omit free-form errors, which can quote inputs, SQL parameters, or credentials.

    Keep local payloads intact for in-process consumers. Apply this policy in both
    transports so callers cannot accidentally send these fields to Segment.
    """
    excluded = {
        name
        for name in type(payload).model_fields
        if name in {"error", "error_message", "exception_message"} or name.endswith("_error_message")
    }
    return payload.model_dump(by_alias=True, exclude_none=True, exclude_unset=True, exclude=excluded)
