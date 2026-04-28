"""Detect write redirects in a shell subcommand.

The pipeline classifies a subcommand by its leading binary, but shell
redirects (``>``, ``>>``, ``2>``, ``&>``, ``*>`` etc.) can quietly turn
a read-only command into a write. ``echo data > foo.txt`` reads as
"echo" (READ_ONLY) but actually writes to ``foo.txt``.

This module is the small, pure helper the pipeline uses to escalate the
intent of such commands to WRITE so ``read_only`` mode catches them.

We intentionally only flag redirects that **write** (``>``, ``>>``,
``2>``, ``2>>``, ``&>``, ``*>``, ``N>`` for any digit). Stdin redirects
(``<``, ``<<``, ``<<<``) are read-only and ignored — they are common
in legitimate read-only commands like ``wc -l < file``.
"""

from __future__ import annotations

import re

# A write redirect is one of:
#   >, >>          stdout
#   N>, N>>        any numbered fd (2>, 3>>, ...)
#   &>, &>>        all streams (bash)
#   *>             all streams (PowerShell)
# Any of these followed by whitespace or filename starts.
_WRITE_REDIRECT_RE = re.compile(
    r"(?:^|[^\\])"  # no-escape boundary
    r"(?:&>>?|\*>>?|\d*>>?)"  # the redirect operator itself
)


def has_write_redirect(command: str) -> bool:
    """Return True if ``command`` contains a write redirect outside quotes."""
    if not command:
        return False
    stripped = _strip_quoted_regions(command)
    return bool(_WRITE_REDIRECT_RE.search(stripped))


def _strip_quoted_regions(command: str) -> str:
    """Replace single- and double-quoted regions with spaces.

    Operators inside quotes are literal text, not shell metachars. We
    can't just delete the regions (that would break length-based
    indexing) so we replace each char with a space.
    """
    out: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(command):
        ch = command[i]
        if quote is not None:
            out.append(" " if ch != quote else ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ('"', "'"):
            quote = ch
            out.append(ch)
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)
