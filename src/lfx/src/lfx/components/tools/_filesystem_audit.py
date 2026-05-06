"""Audit log layer for the FileSystem tool.

Records every public tool call as a single NDJSON line so operators can answer
questions like "who read /data/secrets.md last Tuesday?" without enabling
verbose application logging.

Why NDJSON over a structured logger: the audit stream is a SECURITY artifact,
not a debugging log. It must survive log-level filtering, must be machine
readable line-by-line, and must persist even when the rest of the logger is
silenced. A separate file with explicit append semantics is the lowest-risk
shape.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class AuditRecord:
    """One tool invocation snapshot. Frozen so callers cannot mutate post-build."""

    ts: float
    user_id: str | None
    flow_id: str | None
    action: str
    path: str | None
    ok: bool
    err: str | None

    def to_json_dict(self) -> dict:
        return asdict(self)


class AuditSink(Protocol):
    """Anything that consumes ``AuditRecord`` objects."""

    def write(self, record: AuditRecord) -> None: ...


class NullAuditSink:
    """No-op sink — used when ``LANGFLOW_FS_TOOL_AUDIT_LOG`` is unset.

    Returning a real object (rather than None) lets the component code call
    ``self._audit_sink.write(...)`` unconditionally — no per-call branch.
    """

    def write(self, record: AuditRecord) -> None:  # noqa: ARG002
        return


class NDJSONAuditSink:
    """Append-only NDJSON file sink. One ``write`` ⇒ one line ⇒ one JSON object.

    A single in-process lock serializes appends. POSIX ``O_APPEND`` already
    guarantees atomic appends for writes ≤ PIPE_BUF, but our records are well
    above that limit on most platforms; the lock keeps line boundaries clean
    AND prevents the rare interleave we'd otherwise see on Windows.
    """

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path
        self._lock = threading.Lock()
        log_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: AuditRecord) -> None:
        line = json.dumps(record.to_json_dict(), separators=(",", ":")) + "\n"
        with self._lock, self._log_path.open("a", encoding="utf-8") as fh:
            fh.write(line)


def make_audit_sink(*, audit_log_path: Path | None) -> AuditSink:
    """Pick the right sink for the resolved isolation config."""
    if audit_log_path is None:
        return NullAuditSink()
    return NDJSONAuditSink(audit_log_path)
