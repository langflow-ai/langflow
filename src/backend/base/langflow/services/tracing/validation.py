"""Input validation helpers for trace query parameters.

Validates and sanitizes user-supplied inputs at the API boundary before
they are passed to the repository layer.
"""

from __future__ import annotations

import re

_NON_PRINTABLE_RE = re.compile(r"[^\x20-\x7E]+")


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
    # fast-path for empty string to avoid regex work (preserves original behavior)
    if value == "":
        return None
    # Remove any character outside the ASCII printable range (0x20-0x7E)
    cleaned = _NON_PRINTABLE_RE.sub("", value).strip()
    return cleaned[:max_len] if cleaned else None
