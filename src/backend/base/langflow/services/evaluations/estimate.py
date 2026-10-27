"""Pre-run token and cost range.

The flow part comes from this flow's last finished run when it ran the same flow content (the
most accurate basis), otherwise from the model estimate. The judge part always comes from the model
estimate, because the last run may not have used a judge.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlmodel import col, select

from langflow.services.database.models.evaluation import DatasetItem, EvaluationRun
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.evaluations.dataset_service import item_text
from langflow.services.evaluations.estimate_model import (
    DatasetStats,
    TokenRange,
    estimate_flow,
    estimate_judges,
    flow_llm_nodes,
)
from langflow.services.evaluations.schemas import EstimateRead

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

HISTORY_LOW = 0.8
HISTORY_HIGH = 1.25


async def dataset_stats(session: AsyncSession, dataset_id: UUID) -> DatasetStats:
    # Computed in Python: a JSON column stores None as JSON null, which SQL length/count would miscount.
    rows = (
        await session.exec(
            select(DatasetItem.input, DatasetItem.expected_output).where(DatasetItem.dataset_id == dataset_id)
        )
    ).all()
    expected = [item_text(expected_output) for _, expected_output in rows]
    return DatasetStats(
        items=len(rows),
        input_chars=sum(len(item_text(input_) or "") for input_, _ in rows),
        expected_chars=sum(len(text) for text in expected if text),
        with_expected=sum(1 for text in expected if text),
    )


async def _history_per_row(
    session: AsyncSession, flow_id: UUID, flow_data: dict[str, Any] | None
) -> tuple[float, float | None] | None:
    """Per-row flow usage of the last completed run, only when it ran exactly this flow content."""
    stmt = (
        select(EvaluationRun.summary, FlowVersion.data)
        .join(FlowVersion, col(FlowVersion.id) == EvaluationRun.flow_version_id)
        .where(EvaluationRun.flow_id == flow_id, EvaluationRun.status == "completed")
        .order_by(col(EvaluationRun.created_at).desc())
        .limit(1)
    )
    row = (await session.exec(stmt)).first()
    if row is None or row[1] != flow_data or not isinstance(row[0], dict):
        return None
    summary = row[0]
    counts = summary.get("rows") or {}
    # Errored rows spent little or nothing, so they would drag the per-row figure down.
    rows = (counts.get("total") or 0) - (counts.get("errored") or 0)
    tokens = (summary.get("tokens") or {}).get("flow")
    if rows <= 0 or not tokens:
        return None
    cost = (summary.get("cost_usd") or {}).get("flow")
    return tokens / rows, (cost / rows if cost is not None else None)


def _from_history(per_row: tuple[float, float | None], items: int) -> TokenRange:
    tokens, cost = per_row
    return TokenRange(
        tokens_low=int(tokens * items * HISTORY_LOW),
        tokens_high=int(tokens * items * HISTORY_HIGH),
        cost_low=cost * items * HISTORY_LOW if cost is not None else None,
        cost_high=cost * items * HISTORY_HIGH if cost is not None else None,
    )


def _sum_cost(left: float | None, right: float | None) -> float | None:
    return None if left is None or right is None else round(left + right, 6)


async def estimate_run(
    session: AsyncSession,
    *,
    flow_id: UUID,
    flow_data: dict[str, Any] | None,
    dataset_id: UUID,
    scorers: list[Any],
    judge_max_output_tokens: int,
) -> EstimateRead:
    stats = await dataset_stats(session, dataset_id)
    nodes = flow_llm_nodes(flow_data or {})
    history = await _history_per_row(session, flow_id, flow_data)
    modeled = estimate_flow(nodes, stats)
    flow = _from_history(history, stats.items) if history else modeled
    unpriced = modeled.unpriced if flow.cost_low is None else flow.unpriced
    judge_specs = [spec for spec in scorers if isinstance(spec, dict)]
    judge = estimate_judges(judge_specs, stats, judge_max_output_tokens)
    judge_calls = stats.items * sum(1 for spec in judge_specs if spec.get("type") == "llm_judge")
    return EstimateRead(
        items=stats.items,
        basis="history" if history else "model",
        llm_calls=stats.items * len(nodes) + judge_calls,
        judge_calls=judge_calls,
        flow_tokens_low=flow.tokens_low,
        flow_tokens_high=flow.tokens_high,
        judge_tokens_low=judge.tokens_low,
        judge_tokens_high=judge.tokens_high,
        tokens_low=flow.tokens_low + judge.tokens_low,
        tokens_high=flow.tokens_high + judge.tokens_high,
        cost_low=_sum_cost(flow.cost_low, judge.cost_low),
        cost_high=_sum_cost(flow.cost_high, judge.cost_high),
        unpriced_models=sorted({*unpriced, *judge.unpriced}),
        has_agent=any(node.agent for node in nodes),
    )
