"""Server configuration for the shell MCP server.

Reads settings once from environment variables and exposes an immutable
dataclass. Validation is fail-fast: invalid env values raise at startup
so the server never boots with a misconfigured limit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from lfx.mcp.shell.shell_constants import (
    DEFAULT_MAX_COMMAND_LENGTH,
    DEFAULT_MAX_CONCURRENT,
    DEFAULT_MAX_OUTPUT_BYTES,
    DEFAULT_MAX_TIMEOUT_SECONDS,
    DEFAULT_QUEUE_TIMEOUT_SECONDS,
    ENV_ISOLATION,
    ENV_MAX_COMMAND_LENGTH,
    ENV_MAX_CONCURRENT,
    ENV_MAX_OUTPUT_BYTES,
    ENV_MAX_TIMEOUT,
    ENV_MODE,
    ENV_QUEUE_TIMEOUT,
    ENV_WORKING_DIR,
)


class ShellMode(Enum):
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"


class IsolationMode(Enum):
    """How a per-call working directory is produced.

    ``shared`` keeps the historical behaviour: every call uses the
    configured ``working_directory``. Files persist between calls and
    across tenants -- safe ONLY for single-tenant deployments.

    ``ephemeral`` allocates a fresh ``TemporaryDirectory`` under the
    configured base for every call and deletes it on return. Tenants
    cannot see each other's files. Recommended default for any
    deployment where more than one user shares the backend.
    """

    SHARED = "shared"
    EPHEMERAL = "ephemeral"


@dataclass(frozen=True)
class ShellServerConfig:
    """Immutable runtime configuration.

    Built once via :py:meth:`from_environment` at server startup. Holding
    a frozen instance avoids TOCTOU races where config could change
    between a validation check and the actual subprocess spawn.
    """

    working_directory: str
    mode: ShellMode
    max_timeout: int
    max_output_bytes: int
    max_command_length: int
    max_concurrent: int
    queue_timeout: int
    isolation: IsolationMode

    @classmethod
    def from_environment(cls) -> ShellServerConfig:
        return cls(
            working_directory=_read_working_dir(),
            mode=_read_mode(),
            max_timeout=_read_positive_int(ENV_MAX_TIMEOUT, DEFAULT_MAX_TIMEOUT_SECONDS),
            max_output_bytes=_read_positive_int(ENV_MAX_OUTPUT_BYTES, DEFAULT_MAX_OUTPUT_BYTES),
            max_command_length=_read_positive_int(ENV_MAX_COMMAND_LENGTH, DEFAULT_MAX_COMMAND_LENGTH),
            max_concurrent=_read_positive_int(ENV_MAX_CONCURRENT, DEFAULT_MAX_CONCURRENT),
            queue_timeout=_read_positive_int(ENV_QUEUE_TIMEOUT, DEFAULT_QUEUE_TIMEOUT_SECONDS),
            isolation=_read_isolation(),
        )

    def clamp_timeout(self, requested: int) -> int:
        if requested <= 0:
            msg = f"timeout must be positive, got {requested}"
            raise ValueError(msg)
        return min(requested, self.max_timeout)


def _read_working_dir() -> str:
    """Resolve the sandbox working directory.

    Why no fallback: the entire security model leans on this being a
    deliberate sandbox. If we silently fell back to ``Path.cwd()``, an
    operator who happened to start langflow from ``$HOME`` (or any dir
    holding user files) would hand the agent read access to everything
    under it. Explicit configuration is the only safe contract.
    """
    raw = os.environ.get(ENV_WORKING_DIR)
    if not raw:
        msg = (
            f"{ENV_WORKING_DIR} must be set to an existing sandbox directory. "
            "Refusing to default to the current working directory because that "
            "would expose whatever files are under it to shell tool callers."
        )
        raise ValueError(msg)
    resolved = Path(raw).resolve()
    if not resolved.exists() or not resolved.is_dir():
        msg = f"{ENV_WORKING_DIR} must point to an existing directory: {raw}"
        raise ValueError(msg)
    return str(resolved)


def _read_mode() -> ShellMode:
    """Resolve the read/write mode.

    Why ``READ_ONLY`` is the default: a fresh install handed a ``read_write``
    server can run ``git``, ``pip install``, ``npm``, ``curl``, ``rsync``,
    etc. as the langflow process user. For any deployment with more than
    one tenant that's a wide door to leave open. Operators that need
    write access opt in explicitly.
    """
    raw = os.environ.get(ENV_MODE)
    if raw is None:
        return ShellMode.READ_ONLY
    normalized = raw.strip().lower()
    try:
        return ShellMode(normalized)
    except ValueError as exc:
        valid = ", ".join(m.value for m in ShellMode)
        msg = f"{ENV_MODE} must be one of {valid}, got {raw!r}"
        raise ValueError(msg) from exc


def _read_isolation() -> IsolationMode:
    raw = os.environ.get(ENV_ISOLATION)
    if raw is None:
        return IsolationMode.SHARED
    normalized = raw.strip().lower()
    try:
        return IsolationMode(normalized)
    except ValueError as exc:
        valid = ", ".join(m.value for m in IsolationMode)
        msg = f"{ENV_ISOLATION} must be one of {valid}, got {raw!r}"
        raise ValueError(msg) from exc


def _read_positive_int(env_name: str, default: int) -> int:
    raw = os.environ.get(env_name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        msg = f"{env_name} must be a positive integer, got {raw!r}"
        raise ValueError(msg) from exc
    if value <= 0:
        msg = f"{env_name} must be a positive integer, got {value}"
        raise ValueError(msg)
    return value
