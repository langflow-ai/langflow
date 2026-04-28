"""Stage 1 of the validation pipeline — command intent classification.

Maps the leading binary of a shell command to a coarse intent category.
Pure function: takes a string, returns a :class:`CommandIntent`. No I/O,
no globals.

This is intentionally simple — it inspects only the first token. Cases
like ``ls; rm -rf /`` are handled upstream by splitting on shell
operators before each subcommand is classified.

The table mixes POSIX and Windows binaries on purpose. Names rarely
collide between platforms, and treating both the same way means a
pattern like ``del`` is recognised as DESTRUCTIVE even if a Linux user
happens to have a binary by that name on $PATH (defense in depth).
PowerShell cmdlets (verb-noun) are matched case-insensitively because
the real shell ignores case.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from lfx.mcp.shell.shell_types import CommandIntent

if TYPE_CHECKING:
    from collections.abc import Callable

_INTENT_BY_BINARY: dict[str, CommandIntent] = {
    # Read-only inspection
    "ls": CommandIntent.READ_ONLY,
    "cat": CommandIntent.READ_ONLY,
    "less": CommandIntent.READ_ONLY,
    "more": CommandIntent.READ_ONLY,
    "head": CommandIntent.READ_ONLY,
    "tail": CommandIntent.READ_ONLY,
    "grep": CommandIntent.READ_ONLY,
    "egrep": CommandIntent.READ_ONLY,
    "fgrep": CommandIntent.READ_ONLY,
    "rg": CommandIntent.READ_ONLY,
    "find": CommandIntent.READ_ONLY,
    "locate": CommandIntent.READ_ONLY,
    "pwd": CommandIntent.READ_ONLY,
    "echo": CommandIntent.READ_ONLY,
    "printf": CommandIntent.READ_ONLY,
    "which": CommandIntent.READ_ONLY,
    "whereis": CommandIntent.READ_ONLY,
    "stat": CommandIntent.READ_ONLY,
    "file": CommandIntent.READ_ONLY,
    "wc": CommandIntent.READ_ONLY,
    "diff": CommandIntent.READ_ONLY,
    "cmp": CommandIntent.READ_ONLY,
    "env": CommandIntent.READ_ONLY,
    "printenv": CommandIntent.READ_ONLY,
    "date": CommandIntent.READ_ONLY,
    "uname": CommandIntent.READ_ONLY,
    "hostname": CommandIntent.READ_ONLY,
    "whoami": CommandIntent.READ_ONLY,
    "id": CommandIntent.READ_ONLY,
    "ps": CommandIntent.READ_ONLY,
    "top": CommandIntent.READ_ONLY,
    "df": CommandIntent.READ_ONLY,
    "du": CommandIntent.READ_ONLY,
    "free": CommandIntent.READ_ONLY,
    # Write
    "touch": CommandIntent.WRITE,
    "mkdir": CommandIntent.WRITE,
    "cp": CommandIntent.WRITE,
    "mv": CommandIntent.WRITE,
    "ln": CommandIntent.WRITE,
    "chmod": CommandIntent.WRITE,
    "chown": CommandIntent.WRITE,
    "chgrp": CommandIntent.WRITE,
    "tar": CommandIntent.WRITE,
    "zip": CommandIntent.WRITE,
    "unzip": CommandIntent.WRITE,
    "gzip": CommandIntent.WRITE,
    "gunzip": CommandIntent.WRITE,
    "git": CommandIntent.WRITE,
    "sed": CommandIntent.WRITE,
    "awk": CommandIntent.WRITE,
    # Destructive
    "rm": CommandIntent.DESTRUCTIVE,
    "rmdir": CommandIntent.DESTRUCTIVE,
    "shred": CommandIntent.DESTRUCTIVE,
    "mkfs": CommandIntent.DESTRUCTIVE,
    "dd": CommandIntent.DESTRUCTIVE,
    "fdisk": CommandIntent.DESTRUCTIVE,
    "parted": CommandIntent.DESTRUCTIVE,
    "wipefs": CommandIntent.DESTRUCTIVE,
    # Network
    "curl": CommandIntent.NETWORK,
    "wget": CommandIntent.NETWORK,
    "ssh": CommandIntent.NETWORK,
    "scp": CommandIntent.NETWORK,
    "rsync": CommandIntent.NETWORK,
    "nc": CommandIntent.NETWORK,
    "ncat": CommandIntent.NETWORK,
    "netcat": CommandIntent.NETWORK,
    "ping": CommandIntent.NETWORK,
    "ping6": CommandIntent.NETWORK,
    "telnet": CommandIntent.NETWORK,
    "ftp": CommandIntent.NETWORK,
    "sftp": CommandIntent.NETWORK,
    # Process management
    "kill": CommandIntent.PROCESS_MANAGEMENT,
    "killall": CommandIntent.PROCESS_MANAGEMENT,
    "pkill": CommandIntent.PROCESS_MANAGEMENT,
    "nohup": CommandIntent.PROCESS_MANAGEMENT,
    # Package management
    "apt": CommandIntent.PACKAGE_MANAGEMENT,
    "apt-get": CommandIntent.PACKAGE_MANAGEMENT,
    "yum": CommandIntent.PACKAGE_MANAGEMENT,
    "dnf": CommandIntent.PACKAGE_MANAGEMENT,
    "pip": CommandIntent.PACKAGE_MANAGEMENT,
    "pip3": CommandIntent.PACKAGE_MANAGEMENT,
    "pipx": CommandIntent.PACKAGE_MANAGEMENT,
    "uv": CommandIntent.PACKAGE_MANAGEMENT,
    "poetry": CommandIntent.PACKAGE_MANAGEMENT,
    "npm": CommandIntent.PACKAGE_MANAGEMENT,
    "yarn": CommandIntent.PACKAGE_MANAGEMENT,
    "pnpm": CommandIntent.PACKAGE_MANAGEMENT,
    "brew": CommandIntent.PACKAGE_MANAGEMENT,
    "snap": CommandIntent.PACKAGE_MANAGEMENT,
    "gem": CommandIntent.PACKAGE_MANAGEMENT,
    # System admin
    "sudo": CommandIntent.SYSTEM_ADMIN,
    "su": CommandIntent.SYSTEM_ADMIN,
    "doas": CommandIntent.SYSTEM_ADMIN,
    "systemctl": CommandIntent.SYSTEM_ADMIN,
    "service": CommandIntent.SYSTEM_ADMIN,
    "useradd": CommandIntent.SYSTEM_ADMIN,
    "userdel": CommandIntent.SYSTEM_ADMIN,
    "usermod": CommandIntent.SYSTEM_ADMIN,
    "passwd": CommandIntent.SYSTEM_ADMIN,
    "iptables": CommandIntent.SYSTEM_ADMIN,
    "ufw": CommandIntent.SYSTEM_ADMIN,
    "mount": CommandIntent.SYSTEM_ADMIN,
    "umount": CommandIntent.SYSTEM_ADMIN,
    "shutdown": CommandIntent.SYSTEM_ADMIN,
    "reboot": CommandIntent.SYSTEM_ADMIN,
    "halt": CommandIntent.SYSTEM_ADMIN,
    # ---- Windows (cmd.exe) ----
    # Read-only inspection
    "dir": CommandIntent.READ_ONLY,
    "type": CommandIntent.READ_ONLY,
    "where": CommandIntent.READ_ONLY,
    "tasklist": CommandIntent.READ_ONLY,
    "ver": CommandIntent.READ_ONLY,
    "vol": CommandIntent.READ_ONLY,
    "tree": CommandIntent.READ_ONLY,
    "fc": CommandIntent.READ_ONLY,
    "comp": CommandIntent.READ_ONLY,
    "findstr": CommandIntent.READ_ONLY,
    "systeminfo": CommandIntent.READ_ONLY,
    # Write
    "copy": CommandIntent.WRITE,
    "xcopy": CommandIntent.WRITE,
    "robocopy": CommandIntent.WRITE,
    "mklink": CommandIntent.WRITE,
    "md": CommandIntent.WRITE,
    "icacls": CommandIntent.WRITE,
    "attrib": CommandIntent.WRITE,
    # Note: ``move`` and ``set`` collide with possible POSIX names; on
    # Linux they are uncommon as standalone commands so we accept the
    # Windows semantics as the canonical mapping.
    "move": CommandIntent.WRITE,
    # Destructive
    "del": CommandIntent.DESTRUCTIVE,
    "erase": CommandIntent.DESTRUCTIVE,
    "rd": CommandIntent.DESTRUCTIVE,
    "format": CommandIntent.DESTRUCTIVE,
    "cipher": CommandIntent.DESTRUCTIVE,
    # Network
    "tracert": CommandIntent.NETWORK,
    "nslookup": CommandIntent.NETWORK,
    "ipconfig": CommandIntent.NETWORK,
    "netstat": CommandIntent.NETWORK,
    "arp": CommandIntent.NETWORK,
    "route": CommandIntent.NETWORK,
    "tftp": CommandIntent.NETWORK,
    # Process management
    "taskkill": CommandIntent.PROCESS_MANAGEMENT,
    # Package management
    "choco": CommandIntent.PACKAGE_MANAGEMENT,
    "winget": CommandIntent.PACKAGE_MANAGEMENT,
    "scoop": CommandIntent.PACKAGE_MANAGEMENT,
    # System admin
    "net": CommandIntent.SYSTEM_ADMIN,
    "sc": CommandIntent.SYSTEM_ADMIN,
    "runas": CommandIntent.SYSTEM_ADMIN,
    "reg": CommandIntent.SYSTEM_ADMIN,
    "wmic": CommandIntent.SYSTEM_ADMIN,
    "bcdedit": CommandIntent.SYSTEM_ADMIN,
    "gpupdate": CommandIntent.SYSTEM_ADMIN,
    "secedit": CommandIntent.SYSTEM_ADMIN,
    "diskpart": CommandIntent.SYSTEM_ADMIN,
    "fsutil": CommandIntent.SYSTEM_ADMIN,
    "vssadmin": CommandIntent.SYSTEM_ADMIN,
    "wevtutil": CommandIntent.SYSTEM_ADMIN,
    # ``setx`` always writes to persistent env. ``set`` itself is
    # contextual (see _classify_set below).
    "setx": CommandIntent.WRITE,
}

# ---- PowerShell cmdlets (matched case-insensitively) ------------------------
# PowerShell follows a Verb-Noun convention. Rather than enumerate every
# possible cmdlet, we classify by verb prefix.
_POWERSHELL_VERB_INTENTS: dict[str, CommandIntent] = {
    # Read-only verbs
    "get": CommandIntent.READ_ONLY,
    "select": CommandIntent.READ_ONLY,
    "where": CommandIntent.READ_ONLY,
    "foreach": CommandIntent.READ_ONLY,
    "measure": CommandIntent.READ_ONLY,
    "test": CommandIntent.READ_ONLY,
    "find": CommandIntent.READ_ONLY,
    "show": CommandIntent.READ_ONLY,
    "read": CommandIntent.READ_ONLY,
    "compare": CommandIntent.READ_ONLY,
    # Write verbs
    "set": CommandIntent.WRITE,
    "add": CommandIntent.WRITE,
    "new": CommandIntent.WRITE,
    "out": CommandIntent.WRITE,
    "tee": CommandIntent.WRITE,
    "rename": CommandIntent.WRITE,
    "copy": CommandIntent.WRITE,
    "move": CommandIntent.WRITE,
    "export": CommandIntent.WRITE,
    "import": CommandIntent.WRITE,
    # Destructive verbs
    "remove": CommandIntent.DESTRUCTIVE,
    "clear": CommandIntent.DESTRUCTIVE,
    "uninstall": CommandIntent.DESTRUCTIVE,
    # Network verbs
    "invoke": CommandIntent.NETWORK,  # Invoke-WebRequest, Invoke-RestMethod
    "connect": CommandIntent.NETWORK,
    "disconnect": CommandIntent.NETWORK,
    # Process management
    "start": CommandIntent.PROCESS_MANAGEMENT,
    "stop": CommandIntent.PROCESS_MANAGEMENT,
    "restart": CommandIntent.PROCESS_MANAGEMENT,
    "wait": CommandIntent.PROCESS_MANAGEMENT,
    "suspend": CommandIntent.PROCESS_MANAGEMENT,
    "resume": CommandIntent.PROCESS_MANAGEMENT,
    # Package management
    "install": CommandIntent.PACKAGE_MANAGEMENT,
    "update": CommandIntent.PACKAGE_MANAGEMENT,
    "save": CommandIntent.PACKAGE_MANAGEMENT,
}

# A cmdlet name like "Invoke-WebRequest" is recognized iff it has the
# Verb-Noun pattern with a known verb on the left.
_POWERSHELL_CMDLET_RE = re.compile(r"^([A-Za-z]+)-[A-Za-z][A-Za-z0-9_]*$")


def classify_command(command: str) -> CommandIntent:
    """Classify the leading binary of ``command``.

    Returns ``CommandIntent.UNKNOWN`` for empty input or unrecognized
    binaries — callers decide whether ``UNKNOWN`` is fail-closed.
    """
    leading = _leading_binary(command)
    if leading is None:
        return CommandIntent.UNKNOWN
    # Direct match (case-insensitive — Windows shells ignore case and
    # POSIX names are all-lowercase by convention).
    lowered = leading.lower()
    contextual = _CONTEXTUAL_CLASSIFIERS.get(lowered)
    if contextual is not None:
        return contextual(command)
    direct = _INTENT_BY_BINARY.get(lowered)
    if direct is not None:
        return direct
    # Family binaries like mkfs.ext4 / mkfs.xfs share intent with the base name.
    # On Windows we also strip ``.exe``, ``.bat``, ``.cmd``, etc.
    base = lowered.split(".", 1)[0]
    contextual = _CONTEXTUAL_CLASSIFIERS.get(base)
    if contextual is not None:
        return contextual(command)
    direct = _INTENT_BY_BINARY.get(base)
    if direct is not None:
        return direct
    # PowerShell cmdlet — Verb-Noun pattern.
    match = _POWERSHELL_CMDLET_RE.match(leading)
    if match is not None:
        verb = match.group(1).lower()
        powershell_intent = _POWERSHELL_VERB_INTENTS.get(verb)
        if powershell_intent is not None:
            return powershell_intent
    return CommandIntent.UNKNOWN


# ---- Contextual classifiers --------------------------------------------------
# Some shell builtins change intent depending on their arguments. ``set``
# is the canonical example: ``set`` and ``set FOO`` are read-only on both
# cmd.exe and POSIX sh, while ``set FOO=value`` writes the env.
_BINARY_AND_AT_LEAST_ONE_ARG = 2


def _classify_set(command: str) -> CommandIntent:
    """Return WRITE if the args contain an assignment, READ_ONLY otherwise."""
    # Drop the leading binary, look at the remainder for ``NAME=value``.
    parts = command.strip().split(maxsplit=1)
    if len(parts) < _BINARY_AND_AT_LEAST_ONE_ARG:
        return CommandIntent.READ_ONLY
    rest = parts[1]
    # ``set FOO=bar``: the first token of ``rest`` contains ``=``.
    first_token = rest.split(maxsplit=1)[0]
    return CommandIntent.WRITE if "=" in first_token else CommandIntent.READ_ONLY


_CONTEXTUAL_CLASSIFIERS: dict[str, Callable[[str], CommandIntent]] = {
    "set": _classify_set,
}


def _leading_binary(command: str) -> str | None:
    stripped = command.strip()
    if not stripped:
        return None
    head = stripped.split(maxsplit=1)[0]
    return PurePosixPath(head).name or head
