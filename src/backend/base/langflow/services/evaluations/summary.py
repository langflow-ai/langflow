"""Run-level aggregates computed once, after the last row."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Protocol

from sqlmodel import select

from langflow.services.database.models.evaluation import EvaluationResult

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


class SummaryRow(Protocol):
    scores: dict
    error: str | None
    passed: bool | None
    duration_ms: int
    tokens_flow: int | None
    tokens_judge: int | None
    cost_flow: float | None
    cost_judge: float | None


_SUMMARY_COLUMNS = (
    EvaluationResult.scores,
    EvaluationResult.error,
    EvaluationResult.passed,
    EvaluationResult.duration_ms,
    EvaluationResult.tokens_flow,
    EvaluationResult.tokens_judge,
    EvaluationResult.cost_flow,
    EvaluationResult.cost_judge,
)


async def summary_rows(session: AsyncSession, run_id: UUID) -> list[SummaryRow]:
    """Only the columns the summary reads: outputs can be 20k characters per row."""
    stmt = select(*_SUMMARY_COLUMNS).where(EvaluationResult.run_id == run_id)
    return list((await session.exec(stmt)).all())


def percentile(values: Sequence[float], fraction: float) -> float | None:
    """Nearest-rank percentile; None for an empty sequence."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def _stats(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "p50": None, "p90": None}
    return {
        "mean": round(sum(values) / len(values), 4),
        "p50": percentile(values, 0.5),
        "p90": percentile(values, 0.9),
    }


def _sum_or_none(values: Iterable[float | None], *, required: bool) -> float | None:
    """Sum the known values; None when a required value is unknown, so a partial total never looks complete."""
    total = 0.0
    seen = False
    for value in values:
        if value is None:
            if required:
                return None
            continue
        total += value
        seen = True
    return round(total, 6) if seen else None


def build_summary(results: Sequence[SummaryRow], scorer_names: Sequence[str]) -> dict[str, Any]:
    scores: dict[str, dict[str, float | None]] = {}
    for name in scorer_names:
        values = [
            float(entry["value"])
            for result in results
            if isinstance(entry := (result.scores or {}).get(name), dict) and entry.get("value") is not None
        ]
        scores[name] = _stats(values)
    finished = [result for result in results if result.error is None]
    decided = [result for result in results if result.passed is not None]
    passed = sum(1 for result in decided if result.passed)
    flow_tokens = [result.tokens_flow for result in results]
    judge_tokens = [result.tokens_judge for result in results]
    flow_costs = [result.cost_flow for result in results if result.tokens_flow]
    judge_costs = [result.cost_judge for result in results if result.tokens_judge]
    flow_cost = _sum_or_none(flow_costs, required=True)
    judge_cost = _sum_or_none(judge_costs, required=True)
    tokens_flow = int(sum(t or 0 for t in flow_tokens))
    tokens_judge = int(sum(t or 0 for t in judge_tokens))
    return {
        "scores": scores,
        "duration_ms": _stats([float(result.duration_ms) for result in finished]),
        "tokens": {"flow": tokens_flow, "judge": tokens_judge, "total": tokens_flow + tokens_judge},
        "cost_usd": {
            "flow": flow_cost,
            "judge": judge_cost,
            "total": None if flow_cost is None and judge_cost is None else (flow_cost or 0.0) + (judge_cost or 0.0),
            "complete": (flow_cost is not None or not flow_costs) and (judge_cost is not None or not judge_costs),
        },
        "pass_rate": round(passed / len(decided), 4) if decided else None,
        "rows": {"total": len(results), "errored": len(results) - len(finished), "decided": len(decided)},
    }
