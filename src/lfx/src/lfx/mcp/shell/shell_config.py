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
    DEFAULT_MAX_OUTPUT_BYTES,
    DEFAULT_MAX_TIMEOUT_SECONDS,
    ENV_MAX_COMMAND_LENGTH,
    ENV_MAX_OUTPUT_BYTES,
    ENV_MAX_TIMEOUT,
    ENV_MODE,
    ENV_WORKING_DIR,
)


class ShellMode(Enum):
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"


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

    @classmethod
    def from_environment(cls) -> ShellServerConfig:
        return cls(
            working_directory=_read_working_dir(),
            mode=_read_mode(),
            max_timeout=_read_positive_int(ENV_MAX_TIMEOUT, DEFAULT_MAX_TIMEOUT_SECONDS),
            max_output_bytes=_read_positive_int(ENV_MAX_OUTPUT_BYTES, DEFAULT_MAX_OUTPUT_BYTES),
            max_command_length=_read_positive_int(ENV_MAX_COMMAND_LENGTH, DEFAULT_MAX_COMMAND_LENGTH),
        )

    def clamp_timeout(self, requested: int) -> int:
        if requested <= 0:
            msg = f"timeout must be positive, got {requested}"
            raise ValueError(msg)
        return min(requested, self.max_timeout)


def _read_working_dir() -> str:
    raw = os.environ.get(ENV_WORKING_DIR)
    candidate = Path(raw) if raw else Path.cwd()
    resolved = candidate.resolve()
    if not resolved.exists() or not resolved.is_dir():
        msg = f"{ENV_WORKING_DIR} must point to an existing directory: {candidate}"
        raise ValueError(msg)
    return str(resolved)


def _read_mode() -> ShellMode:
    raw = os.environ.get(ENV_MODE)
    if raw is None:
        return ShellMode.READ_WRITE
    normalized = raw.strip().lower()
    try:
        return ShellMode(normalized)
    except ValueError as exc:
        valid = ", ".join(m.value for m in ShellMode)
        msg = f"{ENV_MODE} must be one of {valid}, got {raw!r}"
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
