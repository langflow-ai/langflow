"""Detect shell command substitution constructs.

Both POSIX shells and PowerShell expand ``$(...)`` to "the output of
the inner command". POSIX shells additionally interpret backticks
``` `...` ``` the same way. Either construct embeds an arbitrary
command we cannot statically validate, so we refuse them outright at
the pipeline level.

Single-quoted regions are exempt: POSIX ``'$(foo)'`` is literal text,
not a substitution. Double-quoted regions DO expand and must be
checked.
"""

from __future__ import annotations


def has_command_substitution(command: str) -> bool:
    """Return True if ``command`` contains a substitution outside single quotes."""
    if not command:
        return False
    quote: str | None = None
    i = 0
    n = len(command)
    while i < n:
        ch = command[i]
        if quote == "'":
            # POSIX single-quoted: literal until closing quote. No
            # escapes allowed inside.
            if ch == "'":
                quote = None
            i += 1
            continue
        if quote == '"':
            # Double-quoted: substitution still expands here.
            if ch == '"':
                quote = None
            elif _is_substitution_opener(command, i):
                return True
            i += 1
            continue
        if ch in ('"', "'"):
            quote = ch
            i += 1
            continue
        if _is_substitution_opener(command, i):
            return True
        i += 1
    return False


def _is_substitution_opener(command: str, i: int) -> bool:
    ch = command[i]
    if ch == "`":
        return True
    # ``$(`` opens both command substitution and arithmetic expansion
    # (``$((``). We treat both as substitution — arithmetic is rare in
    # MCP-driven commands and the false positive is a safer trade than
    # missing a command-substitution case.
    return ch == "$" and i + 1 < len(command) and command[i + 1] == "("
