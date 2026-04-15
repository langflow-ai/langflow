"""Input validation helpers for trace query parameters.

Validates and sanitizes user-supplied inputs at the API boundary before
they are passed to the repository layer.
"""

from __future__ import annotations


def sanitize_query_string(value: str | None, max_len: int = 50) -> str | None:
    """Sanitize a user-supplied query string for safe use in database queries.

    Strips non-printable characters and truncates to ``max_len`` characters.
    Rejects by default: only printable ASCII (0x20-0x7E) is accepted.

    Args:
        value: Raw query string from the request.
        max_len: Maximum allowed length after stripping.

    Returns:
        Sanitized string, or ``None`` if the input was ``None`` or empty.
    """
    if value is None:
        return None
    cleaned = "".join(ch for ch in value if " " <= ch <= "~").strip()
    return cleaned[:max_len] if cleaned else None
