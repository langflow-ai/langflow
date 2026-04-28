"""Stage 2 of the validation pipeline — destructive pattern detection.

Compares the input against a curated list of regex patterns for known
catastrophic commands (whole-system rm, mkfs/dd over devices, fork
bombs, redirects into block devices, power-off). Anything matching is
rejected before execution.

Pure function: takes a string, returns a :class:`ValidationResult`.
"""

from __future__ import annotations

import re

from lfx.mcp.shell.shell_types import RejectionReason, ValidationResult

# Each entry is a tuple ``(label, compiled_regex)``. The label is what
# we surface in the rejection message; the regex describes the family
# of dangerous commands we want to refuse outright.
_DANGER_ROOT_DIRS = r"(?:etc|usr|var|bin|sbin|boot|dev|proc|sys|root|home|lib|lib64)"

# Windows roots we never let recursive ops touch. We accept either ``\``
# or ``/`` after the colon — cmd accepts both as separators in modern
# versions and PowerShell treats them interchangeably.
_WIN_DRIVE = r"[A-Za-z]:"
_WIN_DANGER_DIRS = r"(?:Windows|System32|Program\s+Files(?:\s*\(x86\))?|Users|ProgramData)"

_DESTRUCTIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "rm -rf on root or home",
        re.compile(
            r"(?:^|[\s;|&])"  # boundary (no quotes here — keeps quoted strings safe)
            r"(?:sudo\s+)?"
            r"rm\s+(?:-[rRfF]+\s*)+"  # rm with -rf flags in any combo
            r"(?:--no-preserve-root\s+)?"
            r"(?:"
            r"/\s*$"  # rm -rf /
            r"|/\*"  # rm -rf /*
            rf"|/{_DANGER_ROOT_DIRS}(?:\b|/)"  # rm -rf /etc[/...]
            r"|~(?:\s|$|/)"  # rm -rf ~
            r"|\$HOME(?:\s|$|/)"  # rm -rf $HOME
            r")",
        ),
    ),
    (
        # Defense-in-depth against shell glob/brace expansion. The shell
        # expands ``rm -rf /{etc,var}`` to ``rm -rf /etc /var`` *before*
        # this regex sees the line, so we have to refuse any glob
        # metachar (``*``, ``?``, ``[``, ``{``) close enough to ``/``
        # that it can plausibly expand to a system root.
        "rm -rf with glob/brace expansion near root",
        re.compile(
            r"(?:^|[\s;|&])"
            r"(?:sudo\s+)?"
            r"rm\s+(?:-[rRfF]+\s*)+"
            r"(?:--no-preserve-root\s+)?"
            r"/[A-Za-z]{0,3}[?*\[\]{}]",
        ),
    ),
    (
        "mkfs over device",
        re.compile(r"(?:^|[\s;|&])(?:sudo\s+)?mkfs(?:\.[a-z0-9]+)?\s+/dev/"),
    ),
    (
        "dd writing to device",
        re.compile(r"(?:^|[\s;|&])(?:sudo\s+)?dd\s+[^|;&]*\bof=/dev/"),
    ),
    (
        "fork bomb",
        re.compile(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),
    ),
    (
        "recursive permission change on system root",
        re.compile(
            r"(?:^|[\s;|&])(?:sudo\s+)?"
            r"(?:chmod|chown|chgrp)\s+(?:-[rR]\S*\s+)+\S*\s+"
            r"(?:"
            r"/\s*$"
            rf"|/{_DANGER_ROOT_DIRS}(?:\b|/)"
            r")",
        ),
    ),
    (
        "redirect into block device",
        re.compile(r">\s*/dev/(?:sd[a-z]|nvme\d+n\d+|hd[a-z])\b"),
    ),
    (
        "power management",
        re.compile(
            r"(?:^|[\s;|&])(?:sudo\s+)?(?:shutdown|reboot|halt|poweroff)\b"
            r"|(?:^|[\s;|&])init\s+[06]\b",
        ),
    ),
    # ---- Windows-flavoured destructive patterns ----
    (
        "format drive",
        # ``format`` accepts flags before or after the drive letter
        # (``format /Q C:`` and ``format C: /Q`` are both valid). We
        # use a lookahead so the drive can appear anywhere in the
        # command's args, not only immediately after the binary.
        re.compile(
            r"(?:^|[\s;|&])format(?:\.com)?\b"
            rf"(?=[^|;&]*?\s{_WIN_DRIVE}(?:[\\/]|\s|$))"
            rf"[^|;&]*?{_WIN_DRIVE}",
            re.IGNORECASE,
        ),
    ),
    (
        "recursive del/erase on drive root or system folder",
        # del/erase is only catastrophic with /S (recursive). Without /S
        # it deletes named files only — same risk profile as ``rm`` without
        # ``-r`` on POSIX, which we also let through.
        re.compile(
            r"(?:^|[\s;|&])(?:del|erase)\b"
            r"(?=[^|;&]*?\s/[Ss]\b)"  # lookahead: /S flag must appear
            r"[^|;&]*?"
            rf"(?:{_WIN_DRIVE}[\\/](?:\*|{_WIN_DANGER_DIRS})"
            rf"|{_WIN_DRIVE}[\\/]?(?=\s|$))",
            re.IGNORECASE,
        ),
    ),
    (
        "recursive rd/rmdir on drive root or system folder",
        re.compile(
            r"(?:^|[\s;|&])(?:rd|rmdir)\b"
            r"(?=[^|;&]*?\s/[Ss]\b)"
            r"[^|;&]*?"
            rf"(?:{_WIN_DRIVE}[\\/](?:{_WIN_DANGER_DIRS})"
            rf"|{_WIN_DRIVE}[\\/]?(?=\s|$))",
            re.IGNORECASE,
        ),
    ),
    (
        # Same defense-in-depth for Windows recursive delete with glob
        # in shallow drive path (``del /S /Q C:\W*`` expands to
        # ``C:\Windows``, ``rd /S /Q C:\?indows`` to the same).
        "Windows recursive delete with glob/brace near drive root",
        re.compile(
            r"(?:^|[\s;|&])(?:del|erase|rd|rmdir)\b"
            r"(?=[^|;&]*?\s/[Ss]\b)"
            r"[^|;&]*?"
            rf"{_WIN_DRIVE}[\\/][A-Za-z]{{0,3}}[?*\[\]{{}}]",
            re.IGNORECASE,
        ),
    ),
    (
        "PowerShell Remove-Item with glob/brace near drive root",
        re.compile(
            r"(?:^|[\s;|&])Remove-Item\b[^|;&]*?-Recurse\b[^|;&]*?-Force\b"
            rf"[^|;&]*?{_WIN_DRIVE}[\\/][A-Za-z]{{0,3}}[?*\[\]{{}}]"
            r"|(?:^|[\s;|&])Remove-Item\b[^|;&]*?-Force\b[^|;&]*?-Recurse\b"
            rf"[^|;&]*?{_WIN_DRIVE}[\\/][A-Za-z]{{0,3}}[?*\[\]{{}}]",
            re.IGNORECASE,
        ),
    ),
    (
        "cipher secure delete",
        re.compile(rf"(?:^|[\s;|&])cipher\s+/w:\s*{_WIN_DRIVE}", re.IGNORECASE),
    ),
    (
        "Windows shutdown / reboot",
        re.compile(r"(?:^|[\s;|&])shutdown(?:\.exe)?\s+[/-][srpf]\b", re.IGNORECASE),
    ),
    (
        "vssadmin delete shadows",
        re.compile(r"(?:^|[\s;|&])vssadmin\s+delete\s+shadows\b", re.IGNORECASE),
    ),
    (
        "registry deletion on sensitive hive",
        re.compile(
            r"(?:^|[\s;|&])reg(?:\.exe)?\s+delete\s+"
            r"(?:HKLM|HKEY_LOCAL_MACHINE|HKCU|HKEY_CURRENT_USER|HKCR|HKEY_CLASSES_ROOT|HKU|HKEY_USERS)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PowerShell Remove-Item on root or home",
        re.compile(
            r"(?:^|[\s;|&])Remove-Item\b[^|;&]*?-Recurse\b[^|;&]*?-Force\b"
            rf"(?:[^|;&]*?(?:{_WIN_DRIVE}[\\/]?(?:\s|$|{_WIN_DANGER_DIRS})"
            r"|\$env:USERPROFILE\b|\$env:APPDATA\b|\$HOME\b))"
            r"|(?:^|[\s;|&])Remove-Item\b[^|;&]*?-Force\b[^|;&]*?-Recurse\b"
            rf"(?:[^|;&]*?(?:{_WIN_DRIVE}[\\/]?(?:\s|$|{_WIN_DANGER_DIRS})"
            r"|\$env:USERPROFILE\b|\$env:APPDATA\b|\$HOME\b))",
            re.IGNORECASE,
        ),
    ),
)


def validate_not_destructive(command: str) -> ValidationResult:
    """Reject the command if it matches any known destructive pattern.

    Operates on the **single subcommand** passed in — composite commands
    must be split by the pipeline before reaching this stage so that
    each segment is checked independently.
    """
    for label, pattern in _DESTRUCTIVE_PATTERNS:
        if pattern.search(command):
            return ValidationResult.reject(
                RejectionReason.DESTRUCTIVE_PATTERN,
                f"Command rejected: matches destructive pattern ({label}): {command!r}",
            )
    return ValidationResult.ok()
