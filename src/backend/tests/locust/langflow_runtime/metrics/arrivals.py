"""Paced closed-loop arrival accounting for performance generators."""

from __future__ import annotations

from dataclasses import dataclass, field

try:
    from gevent.lock import RLock
except ImportError:
    from threading import RLock


@dataclass
class ArrivalAccountant:
    """Track intended vs realized workflow arrivals without catch-up replay."""

    intended: int = 0
    attempted: int = 0
    missed: int = 0
    accepted: int = 0
    started: int = 0
    terminal: int = 0
    successful: int = 0
    miss_reasons: dict[str, int] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def record_intended_slot(self) -> None:
        with self._lock:
            self.intended += 1

    def record_attempt(self) -> None:
        with self._lock:
            self.attempted += 1

    def record_miss(self, reason: str) -> None:
        with self._lock:
            self.missed += 1
            self.miss_reasons[reason] = self.miss_reasons.get(reason, 0) + 1

    def record_accepted(self) -> None:
        with self._lock:
            self.accepted += 1

    def record_started(self) -> None:
        with self._lock:
            self.started += 1

    def record_terminal(self, success: bool) -> None:
        with self._lock:
            self.terminal += 1
            if success:
                self.successful += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "intended": self.intended,
                "attempted": self.attempted,
                "missed": self.missed,
                "accepted": self.accepted,
                "started": self.started,
                "terminal": self.terminal,
                "successful": self.successful,
                "miss_reasons": dict(self.miss_reasons),
            }
