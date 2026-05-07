"""Split a shell command into subcommands on top-level operators.

A "top-level operator" is one of ``;``, ``&&``, ``||``, ``|``, or ``&``
that appears outside of single or double quotes. The split is necessary
so that each segment is fed independently to the validation pipeline —
otherwise composite commands like ``ls; rm -rf /`` could bypass Stage 2.

This is a small, single-purpose tokenizer; it does not attempt to be a
full shell parser (no backticks, no $(...), no escape handling beyond
quote skipping). That is intentional: the validators downstream operate
on lexical tokens too, and an attacker who manages to hide a command
inside ``$(...)`` would still hit Stage 1 classification on the outer
construct.
"""

from __future__ import annotations

_TWO_CHAR_OPS = ("&&", "||")
# Newline (\n) and carriage return (\r) are command terminators in POSIX sh,
# PowerShell, and cmd.exe; omitting them lets ``"ls\nrm x"`` survive as a
# single subcommand and bypass destructive/mode validation.
_ONE_CHAR_OPS = (";", "|", "&", "\n", "\r")


def split_subcommands(command: str) -> list[str]:
    """Return the list of non-empty subcommands."""
    parts: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(command):
        ch = command[i]
        if quote is not None:
            buf.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ('"', "'"):
            quote = ch
            buf.append(ch)
            i += 1
            continue
        # Two-char operator first (avoid splitting && into two |)
        if i + 1 < len(command) and command[i : i + 2] in _TWO_CHAR_OPS:
            parts.append("".join(buf).strip())
            buf = []
            i += 2
            continue
        if ch in _ONE_CHAR_OPS:
            parts.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    parts.append("".join(buf).strip())
    return [p for p in parts if p]
