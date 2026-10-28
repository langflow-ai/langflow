from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger

from langflow.services.evaluations.judge_budget import JudgeRunBudget
from langflow.services.evaluations.scorers import ScoreResult, run_scorer
from langflow.services.evaluations.scorers.llm_judge import (
    RUN_BUDGET_SPENT,
    JudgeOutputLimitError,
    judge_run_budget,
    stops_on_output_limit,
)
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
    stop_reason: str | None = None
    """Set when a scorer asks the whole run to stop (a judge that hit its output limit)."""

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
    judge_budget: JudgeRunBudget | None = None,
) -> RowScores:
    outcome = RowScores()
    if errored or actual is None:
        outcome.passed = row_passed({}, scorers, threshold, errored=True)
        return outcome
    judge_tokens = 0
    judge_cost: float | None = 0.0
    judged = False
    budget = judge_budget if judge_budget is not None else JudgeRunBudget()
    for spec in scorers:
        config = spec.get("config") or {}
        if spec["type"] == "llm_judge" and budget.spent(spec["name"], judge_run_budget(config)):
            outcome.scores[spec["name"]] = ScoreResult(
                value=None, comment=RUN_BUDGET_SPENT.format(budget=judge_run_budget(config))
            )
            if stops_on_output_limit(config):
                outcome.stop_reason = RUN_BUDGET_SPENT.format(budget=judge_run_budget(config))
            continue
        try:
            result = await run_scorer(
                spec,
                question=question,
                actual=actual,
                expected=expected,
                user_id=user_id,
            )
        except JudgeOutputLimitError as exc:
            # Not a scorer failure: the row is left without this score, and the run stops only if asked to.
            result = ScoreResult(
                value=None, comment=str(exc), tokens=exc.tokens, cost=exc.cost, output_tokens=exc.output_tokens
            )
            if stops_on_output_limit(config):
                outcome.stop_reason = str(exc)
        except Exception as exc:  # noqa: BLE001 - a failing scorer leaves the row unscored by it, not failed
            await logger.awarning(f"evals_scorer_failed scorer={spec.get('type')} error={type(exc).__name__}")
            result = ScoreResult(value=None, comment=f"Scorer failed: {str(exc)[:SCORER_ERROR_MAX_CHARS]}")
        outcome.scores[spec["name"]] = result
        if spec["type"] == "llm_judge":
            budget.add(spec["name"], result.output_tokens)
            judged = True
            judge_tokens += result.tokens or 0
            judge_cost = None if judge_cost is None or result.cost is None else judge_cost + result.cost
    if judged:
        outcome.judge_tokens = judge_tokens or None
        outcome.judge_cost = judge_cost if judge_tokens else None
    outcome.passed = row_passed(outcome.scores, scorers, threshold, errored=False)
    return outcome
