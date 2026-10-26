from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from langflow.services.evaluations.scorers.types import ScoreResult


def weighted_score(scores: Mapping[str, ScoreResult], scorers: Sequence[Mapping[str, Any]]) -> float | None:
    """Weighted mean of the scorers that judged the row; None when none of them could."""
    total_weight = 0.0
    total = 0.0
    for spec in scorers:
        result = scores.get(spec["name"])
        if result is None or result.value is None:
            continue
        weight = float(spec.get("weight", 1.0))
        total_weight += weight
        total += weight * result.value
    if total_weight == 0:
        return None
    return total / total_weight


def row_passed(
    scores: Mapping[str, ScoreResult],
    scorers: Sequence[Mapping[str, Any]],
    threshold: float,
    *,
    errored: bool,
) -> bool | None:
    if errored:
        return False
    score = weighted_score(scores, scorers)
    if score is None:
        return None
    return score >= threshold
