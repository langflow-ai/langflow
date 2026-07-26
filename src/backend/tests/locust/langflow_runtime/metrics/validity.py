"""Measurement validity tracking for performance runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class InvalidRunReason(StrEnum):
    GENERATOR_SATURATED = "generator_saturated"
    MISSED_ARRIVAL_RATIO = "missed_arrival_ratio"
    DRAIN_RESIDUAL = "drain_residual"
    CORRECTNESS_FAILURE = "correctness_failure"
    LOCUST_FAILURE_RATIO = "locust_failure_ratio"
    MANUAL_INVALIDATION = "manual_invalidation"


@dataclass
class MeasurementValidity:
    """Accumulates reasons that invalidate a performance measurement."""

    reasons: list[str] = field(default_factory=list)

    def invalidate(self, reason: str | InvalidRunReason) -> None:
        text = str(reason)
        if text not in self.reasons:
            self.reasons.append(text)

    @property
    def is_valid(self) -> bool:
        return not self.reasons

    def to_dict(self) -> dict[str, object]:
        return {"valid": self.is_valid, "reasons": list(self.reasons)}


def check_generator_saturation(cpu_pct: float, limit: float) -> str | None:
    if cpu_pct > limit:
        return InvalidRunReason.GENERATOR_SATURATED
    return None


def check_missed_arrival_ratio(missed: int, intended: int, max_ratio: float) -> str | None:
    if intended <= 0:
        return None
    ratio = missed / intended
    if ratio > max_ratio:
        return InvalidRunReason.MISSED_ARRIVAL_RATIO
    return None
