r"""Stage 4 of the validation pipeline — path validation.

Detects path-leak attempts on both POSIX and Windows shells:

  * Parent-directory traversal (``../`` or ``..\``)
  * Home references (``~``, ``$HOME``, ``%USERPROFILE%``, ``%APPDATA%``,
    ``%HOMEDRIVE%%HOMEPATH%``, ``$env:USERPROFILE``)
  * Absolute paths that resolve outside the configured working directory
    (POSIX absolute, Windows drive letters, UNC ``\\server\share``)

Tokens that are clearly not paths (short flags like ``-n``, ``/Q``, or
plain words) are ignored to keep false positives low.
"""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path, PureWindowsPath

from lfx.mcp.shell.shell_types import RejectionReason, ValidationResult

_HOME_REFERENCES_POSIX = ("~",)
_PARENT_TRAVERSAL = re.compile(r"(?:^|[/\\])\.\.(?:[/\\]|$)")

# Both ``$HOME`` and ``${HOME}`` shell-expand to the same path, so the
# validator must catch both forms. Same logic for any env-var reference
# (``$VAR`` and ``${VAR}``). The ``\{?`` and ``\}?`` make the braces
# optional; when present, both must appear (not enforced by the regex
# itself, but a stray ``${VAR`` token is unusual enough to ignore).
# Match against the *bare* env-var name with no path separator
# requirement — ``cat $HOME`` and ``echo ${HOME}`` are both leaks.
_HOME_REFERENCES_POSIX_PATTERNS = (re.compile(r"\$\{?HOME\}?"),)

# Windows-shaped home references — any token containing one of these
# substrings is rejected. Case-insensitive.
# Three forms covered per env var:
#   * ``%VAR%``     — cmd.exe
#   * ``$env:VAR``  — PowerShell
#   * ``${VAR}``    — bash on Windows (Git Bash, WSL, MSYS2). Caught by
#                     the bare ``\$\{?VAR\}?`` pattern below.
_HOME_REFERENCES_WINDOWS_PATTERNS = (
    re.compile(r"%USERPROFILE%", re.IGNORECASE),
    re.compile(r"%APPDATA%", re.IGNORECASE),
    re.compile(r"%LOCALAPPDATA%", re.IGNORECASE),
    re.compile(r"%HOMEDRIVE%", re.IGNORECASE),
    re.compile(r"%HOMEPATH%", re.IGNORECASE),
    re.compile(r"\$env:USERPROFILE\b", re.IGNORECASE),
    re.compile(r"\$env:APPDATA\b", re.IGNORECASE),
    re.compile(r"\$env:LOCALAPPDATA\b", re.IGNORECASE),
    re.compile(r"\$env:HOMEDRIVE\b", re.IGNORECASE),
    re.compile(r"\$env:HOMEPATH\b", re.IGNORECASE),
    re.compile(r"\$\{?env:HOME\}?", re.IGNORECASE),
    re.compile(r"\$\{?USERPROFILE\}?", re.IGNORECASE),
    re.compile(r"\$\{?APPDATA\}?", re.IGNORECASE),
    re.compile(r"\$\{?LOCALAPPDATA\}?", re.IGNORECASE),
    re.compile(r"\$\{?HOMEDRIVE\}?", re.IGNORECASE),
    re.compile(r"\$\{?HOMEPATH\}?", re.IGNORECASE),
)

# Drive-letter (``C:\``, ``C:/``) and UNC (``\\server\share``) prefixes.
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_WINDOWS_UNC_RE = re.compile(r"^\\\\[^\\]+\\")


def validate_paths(command: str, *, working_directory: str) -> ValidationResult:
    r"""Reject the command if any token references a path outside the cwd.

    ``working_directory`` is treated as the trust boundary. We tokenise
    with ``shlex(posix=False)`` so backslashes inside Windows paths are
    preserved verbatim — POSIX-mode shlex would interpret them as escapes
    and silently strip them, which would let ``..\..\config`` slip past
    the parent-traversal check.
    """
    try:
        raw_tokens = shlex.split(command, posix=False)
    except ValueError:
        # Unbalanced quotes — let the executor surface the syntax error
        # rather than rejecting here.
        return ValidationResult.ok()

    cwd_resolved = Path(working_directory).resolve()
    for raw in raw_tokens:
        token = _strip_outer_quotes(raw)
        violation = _check_token(token, cwd_resolved)
        if violation is not None:
            return ValidationResult.reject(
                RejectionReason.PATH_TRAVERSAL,
                f"Command rejected: path token {token!r} {violation}.",
            )
    return ValidationResult.ok()


_MIN_QUOTED_TOKEN_LEN = 2


def _strip_outer_quotes(token: str) -> str:
    if len(token) >= _MIN_QUOTED_TOKEN_LEN and token[0] == token[-1] and token[0] in ('"', "'"):
        return token[1:-1]
    return token


def _check_token(token: str, cwd: Path) -> str | None:
    if _is_flag_token(token):
        return None
    home_violation = _check_home_reference(token)
    if home_violation is not None:
        return home_violation
    if _PARENT_TRAVERSAL.search(token):
        return "uses parent-directory traversal (../ or ..\\)"
    if _WINDOWS_UNC_RE.match(token):
        return "is a UNC path (\\\\server\\share) outside working_directory"
    if _is_absolute_outside(token, cwd):
        return f"is an absolute path outside working_directory ({cwd})"
    return None


def _is_flag_token(token: str) -> bool:
    """True for shell flags that are never path-like.

    Matches POSIX-style ``-x``, ``--long`` and Windows-style ``/Q``,
    ``/F``, ``/S`` short flags. We do NOT swallow ``/etc`` or
    ``/something/longer`` — those are absolute POSIX paths and must be
    validated.
    """
    if token.startswith("-"):
        return True
    # Windows short flag: exactly /<one-or-two-chars> (e.g. /Q, /A:H, /S)
    return bool(re.fullmatch(r"/[A-Za-z](?::[^/\s]*)?", token))


def _check_home_reference(token: str) -> str | None:
    for ref in _HOME_REFERENCES_POSIX:
        if token == ref or token.startswith((ref + "/", ref + "\\")):
            return f"references home directory ({ref})"
    for pattern in _HOME_REFERENCES_POSIX_PATTERNS:
        if pattern.search(token):
            return f"references home env var ({pattern.pattern})"
    for pattern in _HOME_REFERENCES_WINDOWS_PATTERNS:
        if pattern.search(token):
            return f"references Windows home env var ({pattern.pattern})"
    return None


def _is_absolute_outside(token: str, cwd: Path) -> bool:
    if _WINDOWS_DRIVE_RE.match(token):
        # On a non-Windows host we cannot meaningfully resolve a drive
        # letter — treat any drive-letter path as outside the cwd unless
        # the cwd itself is on the same drive (Windows-only check).
        if os.name != "nt":
            return True
        return _drive_letter_outside_cwd(token, cwd)
    if not token.startswith("/"):
        return False
    candidate = Path(token).resolve()
    try:
        candidate.relative_to(cwd)
    except ValueError:
        return True
    return False


def _drive_letter_outside_cwd(token: str, cwd: Path) -> bool:
    candidate = PureWindowsPath(token)
    cwd_win = PureWindowsPath(str(cwd))
    if candidate.drive.lower() != cwd_win.drive.lower():
        return True
    try:
        candidate.relative_to(cwd_win)
    except ValueError:
        return True
    return False
