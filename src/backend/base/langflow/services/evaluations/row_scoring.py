from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger

from langflow.services.evaluations.scorers import ScoreResult, run_scorer
from langflow.services.evaluations.scorers.pass_rule import row_passed

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

SCORER_ERROR_MAX_CHARS = 300


@dataclass
class RowScores:
    scores: dict[str, ScoreResult] = field(default_factory=dict)
    passed: bool | None = None
    judge_tokens: int | None = None
    judge_cost: float | None = None

    def scores_json(self) -> dict[str, Any]:
        return {name: result.to_json() for name, result in self.scores.items()}


async def score_row(
    *,
    scorers: Sequence[dict[str, Any]],
    threshold: float,
    question: str,
    actual: str | None,
    expected: str | None,
    errored: bool,
    user_id: UUID,
    judge_max_output_tokens: int,
) -> RowScores:
    outcome = RowScores()
    if errored or actual is None:
        outcome.passed = row_passed({}, scorers, threshold, errored=True)
        return outcome
    judge_tokens = 0
    judge_cost: float | None = 0.0
    judged = False
    for spec in scorers:
        try:
            result = await run_scorer(
                spec,
                question=question,
                actual=actual,
                expected=expected,
                user_id=user_id,
                judge_max_output_tokens=judge_max_output_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - a failing scorer leaves the row unscored by it, not failed
            await logger.awarning(f"evals_scorer_failed scorer={spec.get('type')} error={type(exc).__name__}")
            result = ScoreResult(value=None, comment=f"Scorer failed: {str(exc)[:SCORER_ERROR_MAX_CHARS]}")
        outcome.scores[spec["name"]] = result
        if spec["type"] == "llm_judge":
            judged = True
            judge_tokens += result.tokens or 0
            judge_cost = None if judge_cost is None or result.cost is None else judge_cost + result.cost
    if judged:
        outcome.judge_tokens = judge_tokens or None
        outcome.judge_cost = judge_cost if judge_tokens else None
    outcome.passed = row_passed(outcome.scores, scorers, threshold, errored=False)
    return outcome
