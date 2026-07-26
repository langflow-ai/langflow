"""Step-capacity helpers for measured plateaus (package map ``shapes/step_capacity.py``)."""

from __future__ import annotations

from dataclasses import dataclass

from tests.locust.langflow_runtime.metrics.analysis import (
    CandidateKneeBracket,
    PlateauSummary,
    StepCurve,
    build_step_curve,
    suggest_candidate_knee_inputs,
)


@dataclass(frozen=True)
class StepCapacityPoint:
    """One measured step's offered vs achieved load summary."""

    step_index: int
    offered_users_or_rate: float
    achieved_completion_rate: float
    p95_ms: float
    backlog_proxy: float


def plateaus_to_capacity_points(plateaus: list[PlateauSummary]) -> list[StepCapacityPoint]:
    return [
        StepCapacityPoint(
            step_index=plateau.step_index,
            offered_users_or_rate=plateau.users_or_rate,
            achieved_completion_rate=plateau.successful_completion_rate,
            p95_ms=plateau.p95_ms,
            backlog_proxy=plateau.backlog_proxy,
        )
        for plateau in plateaus
    ]


def capacity_curve_and_knee(
    plateaus: list[PlateauSummary],
) -> tuple[list[StepCurve], CandidateKneeBracket | None]:
    """Build the raw step curve and optional manual knee bracket inputs."""
    curve = build_step_curve(plateaus)
    return curve, suggest_candidate_knee_inputs(curve)
