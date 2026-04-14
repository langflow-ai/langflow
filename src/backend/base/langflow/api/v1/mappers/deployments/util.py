from __future__ import annotations


def require_non_empty(value: str | None, error_msg: str) -> str:
    """Return a stripped non-empty string, or raise ``ValueError``."""
    stripped = (value or "").strip()
    if not stripped:
        raise ValueError(error_msg)
    return stripped
