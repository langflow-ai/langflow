"""Paced closed-loop arrival accounting for performance generators."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass

try:
    from gevent.lock import RLock
except ImportError:
    from threading import RLock


@dataclass(frozen=True)
class ArrivalReservation:
    """One scheduled admission slot plus slots skipped without catch-up replay."""

    delay_s: float
    missed_slots: int
    lateness_s: float


class PacedArrivalScheduler:
    """Reserve global monotonic arrival slots shared by all queue users."""

    def __init__(
        self,
        rate_per_s: float,
        *,
        allowed_lateness_s: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if rate_per_s <= 0:
            msg = "rate_per_s must be positive"
            raise ValueError(msg)
        if allowed_lateness_s < 0:
            msg = "allowed_lateness_s must be non-negative"
            raise ValueError(msg)
        self.interval_s = 1.0 / rate_per_s
        self.allowed_lateness_s = allowed_lateness_s
        self._clock = clock
        self._next_slot = clock()
        self._lock = RLock()

    def reserve(self) -> ArrivalReservation:
        """Reserve the next usable slot and count expired slots as misses."""
        with self._lock:
            now = self._clock()
            slot = self._next_slot
            lateness = max(0.0, now - slot)
            missed = 0
            if lateness > self.allowed_lateness_s:
                missed = max(1, math.ceil((lateness - self.allowed_lateness_s) / self.interval_s))
                slot += missed * self.interval_s
            self._next_slot = slot + self.interval_s
            return ArrivalReservation(
                delay_s=max(0.0, slot - now),
                missed_slots=missed,
                lateness_s=max(0.0, now - slot),
            )
