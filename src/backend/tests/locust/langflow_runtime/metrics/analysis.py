"""Step-curve analysis helpers for plateau and knee-point review."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlateauSummary:
    """Aggregated steady-state metrics for one load step."""

    step_index: int
    users_or_rate: float
    duration_s: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    successful_completion_rate: float
    backlog_proxy: float


@dataclass(frozen=True)
class StepCurve:
    """One point on a step ramp curve."""

    step_index: int
    users_or_rate: float
    duration_s: float
    p50: float
    p95: float
    p99: float
    successful_completion_rate: float
    backlog_proxy: float


@dataclass(frozen=True)
class CandidateKneeBracket:
    """Manual analyst bracket around a suspected performance knee — not auto-certified."""

    low_step: int
    high_step: int
    notes: str


def build_step_curve(plateaus: list[PlateauSummary]) -> list[StepCurve]:
    return [
        StepCurve(
            step_index=plateau.step_index,
            users_or_rate=plateau.users_or_rate,
            duration_s=plateau.duration_s,
            p50=plateau.p50_ms,
            p95=plateau.p95_ms,
            p99=plateau.p99_ms,
            successful_completion_rate=plateau.successful_completion_rate,
            backlog_proxy=plateau.backlog_proxy,
        )
        for plateau in plateaus
    ]


def suggest_candidate_knee_inputs(curve: list[StepCurve]) -> CandidateKneeBracket | None:
    """Heuristic knee hint for manual review — never auto-certifies a knee point."""
    if len(curve) < 2:
        return None

    best_jump = 0.0
    best_low = curve[0].step_index
    best_high = curve[1].step_index

    for left, right in zip(curve, curve[1:], strict=False):
        if left.p95 <= 0:
            continue
        jump = (right.p95 - left.p95) / left.p95
        if jump > best_jump:
            best_jump = jump
            best_low = left.step_index
            best_high = right.step_index

    if best_jump < 0.25:
        return None

    return CandidateKneeBracket(
        low_step=best_low,
        high_step=best_high,
        notes=(
            "manual review required: heuristic p95 jump "
            f"{best_jump:.0%} between steps {best_low} and {best_high}; not auto-certified"
        ),
    )
