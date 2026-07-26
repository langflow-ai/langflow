"""Gevent-compatible Server-Sent Events frame parser."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator


class SseError(Exception):
    """Base SSE parsing error."""


class SseTimeoutError(SseError):
    """Deadline exceeded while waiting for SSE frames."""


class SseTruncationError(SseError):
    """Stream ended before a terminal frame was observed."""


class SseOverflowError(SseError):
    """Maximum event count exceeded."""


@dataclass(frozen=True)
class SseEvent:
    event: str
    data: str
    id: str | None = None


@dataclass
class SseDeadlines:
    connect_s: float | None = None
    read_s: float | None = None
    idle_s: float | None = None


@dataclass
class SseTimingStats:
    """First-event and inter-event timing observed while parsing an SSE stream."""

    first_event_s: float | None = None
    inter_event_s: list[float] | None = None

    def record_event(self, elapsed_s: float) -> None:
        if self.first_event_s is None:
            self.first_event_s = elapsed_s
            self.inter_event_s = []
            return
        assert self.inter_event_s is not None
        previous = self.first_event_s if not self.inter_event_s else (self.first_event_s + sum(self.inter_event_s))
        # elapsed_s is since stream start; convert to gap from prior event.
        gap = max(0.0, elapsed_s - previous)
        self.inter_event_s.append(gap)


def _parse_field(line: str) -> tuple[str, str] | None:
    if not line or line.startswith(":"):
        return None
    if ":" in line:
        field, value = line.split(":", 1)
        value = value.removeprefix(" ")
        return field, value
    return line, ""


def parse_sse_events(
    lines: Iterator[str],
    *,
    deadlines: SseDeadlines | None = None,
    max_events: int | None = None,
    terminal_events: set[str] | None = None,
    started_at: float | None = None,
    timing: SseTimingStats | None = None,
) -> Iterator[SseEvent]:
    """Parse ``event:`` / ``data:`` frames from a line iterator.

    Yields :class:`SseEvent` instances. Comment/heartbeat lines (``:``) are ignored.
    Raises :class:`SseTimeoutError`, :class:`SseOverflowError`, or
    :class:`SseTruncationError` on failure modes requested by callers.

    When ``timing`` is provided, records first-event and inter-event latencies.
    """
    deadlines = deadlines or SseDeadlines()
    started = started_at if started_at is not None else time.monotonic()
    last_activity = started
    event_name = "message"
    data_lines: list[str] = []
    event_id: str | None = None
    yielded = 0

    def _check_deadlines() -> None:
        now = time.monotonic()
        if deadlines.connect_s is not None and yielded == 0 and (now - started) > deadlines.connect_s:
            raise SseTimeoutError("connect deadline exceeded before first SSE event")
        if deadlines.read_s is not None and (now - started) > deadlines.read_s:
            raise SseTimeoutError("read deadline exceeded")
        if deadlines.idle_s is not None and (now - last_activity) > deadlines.idle_s:
            raise SseTimeoutError("idle deadline exceeded between SSE events")

    def _dispatch() -> SseEvent | None:
        nonlocal event_name, data_lines, event_id, yielded, last_activity
        if not data_lines and event_name == "message":
            return None
        payload = "\n".join(data_lines)
        out = SseEvent(event=event_name or "message", data=payload, id=event_id)
        event_name = "message"
        data_lines = []
        event_id = None
        yielded += 1
        last_activity = time.monotonic()
        if timing is not None:
            timing.record_event(last_activity - started)
        return out

    while True:
        _check_deadlines()
        try:
            raw = next(lines)
        except StopIteration as exc:
            pending = _dispatch()
            if pending is not None:
                yield pending
            if terminal_events is not None:
                raise SseTruncationError("stream ended before terminal SSE event") from exc
            return

        if raw is None:
            continue

        line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
        line = line.rstrip("\r")

        if line == "":
            pending = _dispatch()
            if pending is not None:
                if max_events is not None and yielded > max_events:
                    raise SseOverflowError(f"max_events={max_events} exceeded")
                yield pending
                if terminal_events is not None and pending.event in terminal_events:
                    return
            continue

        if line.startswith(":"):
            last_activity = time.monotonic()
            continue

        parsed = _parse_field(line)
        if parsed is None:
            continue
        field, value = parsed
        if field == "event":
            event_name = value
        elif field == "data":
            data_lines.append(value)
        elif field == "id":
            event_id = value
        last_activity = time.monotonic()
