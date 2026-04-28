"""Truncate stdout/stderr to a fixed byte budget.

We measure the budget against the UTF-8 byte length so the limit
matches whatever the receiver will actually transport (MCP messages are
carried over JSON, which is itself bounded by stream-level limits).
The truncation marker is always appended verbatim so callers can detect
the cut without inspecting metadata.
"""

from __future__ import annotations

from lfx.mcp.shell.shell_constants import TRUNCATION_MARKER_TEMPLATE


def truncate_output(text: str, *, max_bytes: int) -> tuple[str, bool]:
    """Return ``(text, was_truncated)``.

    If the UTF-8 encoding of ``text`` exceeds ``max_bytes``, slice it
    safely on a character boundary, then append the marker describing
    how many bytes were dropped.
    """
    if not text:
        return "", False
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text, False
    head = encoded[:max_bytes].decode("utf-8", errors="ignore")
    dropped = len(encoded) - len(head.encode("utf-8"))
    marker = TRUNCATION_MARKER_TEMPLATE.format(dropped=dropped)
    return head + marker, True
