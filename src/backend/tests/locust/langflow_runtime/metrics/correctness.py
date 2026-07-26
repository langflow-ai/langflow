"""Correctness validators for performance-suite assertions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CorrectnessResult:
    ok: bool
    reason: str | None = None


_TERMINAL_STREAM_MARKERS = (
    '"event": "end"',
    '"event":"end"',
    "event: end",
    '"event": "error"',
    '"event":"error"',
    "event: error",
)
_TERMINAL_WORKFLOW_STATUSES = frozenset({"completed", "failed", "cancelled", "timed_out"})


def expect_contains(text: str, needle: str) -> CorrectnessResult:
    if needle in text:
        return CorrectnessResult(ok=True)
    return CorrectnessResult(ok=False, reason=f"text missing needle: {needle!r}")


def expect_stream_terminal(body_or_events: str | list[str]) -> CorrectnessResult:
    if isinstance(body_or_events, list):
        combined = "\n".join(body_or_events)
    else:
        combined = body_or_events
    for marker in _TERMINAL_STREAM_MARKERS:
        if marker in combined:
            return CorrectnessResult(ok=True)
    return CorrectnessResult(ok=False, reason="stream did not emit a terminal end/error event")


def expect_workflow_terminal(status: str) -> CorrectnessResult:
    normalized = status.lower()
    if normalized in _TERMINAL_WORKFLOW_STATUSES:
        return CorrectnessResult(ok=True)
    return CorrectnessResult(
        ok=False,
        reason=f"workflow status {status!r} is not terminal (expected one of {sorted(_TERMINAL_WORKFLOW_STATUSES)})",
    )


def expect_hitl_request_id(pending_row: dict[str, Any], job_id: str) -> CorrectnessResult:
    row_job_id = pending_row.get("job_id")
    request_id = pending_row.get("request_id")
    if not request_id:
        return CorrectnessResult(ok=False, reason="pending row missing request_id")
    if str(row_job_id) != str(job_id):
        return CorrectnessResult(
            ok=False,
            reason=f"pending row job_id {row_job_id!r} does not match expected {job_id!r}",
        )
    return CorrectnessResult(ok=True)


def expect_webhook_n_accept_n_complete(accepted: int, completed: int) -> CorrectnessResult:
    if accepted == completed:
        return CorrectnessResult(ok=True)
    return CorrectnessResult(
        ok=False,
        reason=f"webhook accepted ({accepted}) != completed ({completed})",
    )


def expect_chat_ordering(messages: list[Any]) -> CorrectnessResult:
    if not messages:
        return CorrectnessResult(ok=True)
    indices: list[int] = []
    for message in messages:
        if isinstance(message, dict):
            index = message.get("index")
            if index is None:
                index = message.get("sequence")
        else:
            index = getattr(message, "index", None)
            if index is None:
                index = getattr(message, "sequence", None)
        if index is None:
            return CorrectnessResult(ok=False, reason="chat message missing index/sequence")
        indices.append(int(index))
    for pos in range(1, len(indices)):
        if indices[pos] < indices[pos - 1]:
            return CorrectnessResult(
                ok=False,
                reason=f"chat ordering violated at position {pos}: {indices[pos - 1]} -> {indices[pos]}",
            )
    return CorrectnessResult(ok=True)


def expect_kb_retrieval(text: str, known_query_marker: str) -> CorrectnessResult:
    if known_query_marker not in text:
        return CorrectnessResult(ok=False, reason=f"KB retrieval missing marker {known_query_marker!r}")
    return CorrectnessResult(ok=True)


def expect_multiproc_metrics(result_dict: dict[str, Any]) -> CorrectnessResult:
    if "overlap_ms" not in result_dict and "overlap" not in result_dict:
        return CorrectnessResult(ok=False, reason="multiproc result missing overlap metric")
    switches = result_dict.get("vcs")
    if switches is None:
        switches = result_dict.get("switches")
    if switches is None:
        return CorrectnessResult(ok=False, reason="multiproc result missing context-switch counter")
    if int(switches) < 0:
        return CorrectnessResult(ok=False, reason="multiproc context-switch counter is negative")
    return CorrectnessResult(ok=True)


def expect_disk_io_contract(result_dict: dict[str, Any]) -> CorrectnessResult:
    written = result_dict.get("written")
    read = result_dict.get("read")
    size = result_dict.get("size")
    cksum_ok = result_dict.get("cksum_ok")
    if written is None or read is None or size is None:
        return CorrectnessResult(ok=False, reason="disk I/O result missing byte counters")
    if int(written) != int(size) or int(read) != int(size):
        return CorrectnessResult(
            ok=False,
            reason=f"disk I/O byte mismatch: size={size}, written={written}, read={read}",
        )
    if cksum_ok in (False, 0, "0"):
        return CorrectnessResult(ok=False, reason="disk I/O checksum verification failed")
    return CorrectnessResult(ok=True)
