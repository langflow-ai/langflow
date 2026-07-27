"""Locust-free helpers shared by suite users and unit tests."""

from __future__ import annotations

import json
from typing import Any


def require_flow(state: dict[str, Any] | None, fixture_id: str) -> dict[str, Any] | None:
    """Return provisioned flow metadata for ``fixture_id``, or None if unavailable."""
    if not isinstance(state, dict):
        return None
    flows = state.get("flows")
    if not isinstance(flows, dict):
        return None
    entry = flows.get(fixture_id)
    if not isinstance(entry, dict):
        return None
    if not entry.get("flow_id"):
        return None
    return entry


def extract_output_text(payload: Any) -> str:
    """Best-effort extraction of textual workflow output for correctness checks."""
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("text", "output", "result", "message"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                nested = extract_output_text(value)
                if nested:
                    return nested
        outputs = payload.get("outputs")
        if isinstance(outputs, list):
            parts = [extract_output_text(item) for item in outputs]
            return "\n".join(part for part in parts if part)
        if isinstance(outputs, dict):
            return extract_output_text(outputs)
        messages = payload.get("messages")
        if isinstance(messages, list):
            parts = [extract_output_text(item) for item in messages]
            return "\n".join(part for part in parts if part)
        try:
            return json.dumps(payload)
        except (TypeError, ValueError):
            return str(payload)
    if isinstance(payload, list):
        parts = [extract_output_text(item) for item in payload]
        return "\n".join(part for part in parts if part)
    return str(payload)
