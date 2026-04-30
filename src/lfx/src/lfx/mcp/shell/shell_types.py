"""Domain types for the shell MCP server.

Holds enums and frozen dataclasses used to communicate the result of
classification, validation, and execution. Kept dependency-free so all
downstream modules can import without cycles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CommandIntent(Enum):
    """Coarse classification of what a command tries to do.

    Order matters for mode validation: anything other than READ_ONLY is
    blocked under read_only mode.
    """

    READ_ONLY = "read_only"
    WRITE = "write"
    DESTRUCTIVE = "destructive"
    NETWORK = "network"
    PROCESS_MANAGEMENT = "process_management"
    PACKAGE_MANAGEMENT = "package_management"
    SYSTEM_ADMIN = "system_admin"
    UNKNOWN = "unknown"


class RejectionReason(Enum):
    """Stable codes returned to the caller when a command is rejected."""

    DESTRUCTIVE_PATTERN = "destructive_pattern"
    MODE_VIOLATION = "mode_violation"
    PATH_TRAVERSAL = "path_traversal"
    UNKNOWN_CLASSIFICATION = "unknown_classification"
    INPUT_TOO_LARGE = "input_too_large"
    # Refused construct: ``$(...)`` / `` `...` `` / similar shell
    # substitution wrappers that embed an unvalidatable inner command.
    SHELL_SUBSTITUTION_NOT_ALLOWED = "shell_substitution_not_allowed"
    # Server is at its concurrency cap and the call could not acquire a
    # permit before ``queue_timeout`` elapsed. Stable, retryable signal
    # so an agent can back off instead of waiting past the proxy budget.
    QUEUE_FULL = "queue_full"


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of a single validation stage."""

    is_ok: bool
    reason: RejectionReason | None = None
    message: str = ""

    @classmethod
    def ok(cls) -> ValidationResult:
        return cls(is_ok=True)

    @classmethod
    def reject(cls, reason: RejectionReason, message: str) -> ValidationResult:
        return cls(is_ok=False, reason=reason, message=message)


@dataclass(frozen=True)
class ExecutionResult:
    """Final shape returned by the execute_command tool.

    Successful runs leave ``rejected`` as False and the rejection fields
    are omitted from the serialized payload to keep responses compact.
    """

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    rejected: bool = False
    rejection_reason: RejectionReason | None = None
    truncated: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
        }
        if self.rejected:
            payload["rejected"] = True
            payload["rejection_reason"] = self.rejection_reason.value if self.rejection_reason is not None else None
        if self.truncated:
            payload["truncated"] = True
        if self.extra:
            payload.update(self.extra)
        return payload
