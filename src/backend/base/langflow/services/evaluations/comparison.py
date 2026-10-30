"""Compare model variants: the dataset runs once per variant, on the same flow version, one run after another.

Variants run in sequence, not side by side: an evaluation allows one active run, and variants sharing
providers and row slots would skew each other's latency, which is one of the things being compared.
The plan rides on each run's config, so the run that finishes knows which variant starts next.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from sqlmodel import col, select

from langflow.services.database.models.evaluation import Dataset, Evaluation, EvaluationRun
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from langflow.services.evaluations.errors import EvalsError
from langflow.services.evaluations.schemas import ModelOverride

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

COMPARISON_KEY = "comparison"
# A failed variant (stopped early, a broken model) is still a result worth comparing; a cancel stops the rest.
CONTINUE_AFTER = frozenset({"completed", "failed"})


def new_comparison(variants: Sequence[Sequence[ModelOverride]]) -> dict[str, Any] | None:
    """The comparison config of the first run, or None when there is nothing to compare."""
    if len(variants) < 2:  # noqa: PLR2004 - a comparison needs two sides
        return None
    return {
        "id": str(uuid.uuid4()),
        "index": 0,
        "variants": [[override.model_dump() for override in variant] for variant in variants],
    }


def next_step(config: dict[str, Any] | None) -> tuple[dict[str, Any], list[ModelOverride]] | None:
    """The comparison config and overrides of the variant after this run's, or None when it was the last."""
    comparison = (config or {}).get(COMPARISON_KEY)
    if not isinstance(comparison, dict):
        return None
    variants = comparison.get("variants")
    index = comparison.get("index")
    if not isinstance(variants, list) or not isinstance(index, int) or index + 1 >= len(variants):
        return None
    overrides = [ModelOverride.model_validate(item) for item in variants[index + 1]]
    return {**comparison, "index": index + 1}, overrides


async def _already_started(session: AsyncSession, run: EvaluationRun, comparison: dict[str, Any]) -> bool:
    later = (
        await session.exec(
            select(EvaluationRun.config).where(
                EvaluationRun.evaluation_id == run.evaluation_id, col(EvaluationRun.created_at) >= run.created_at
            )
        )
    ).all()
    return any(
        (config or {}).get(COMPARISON_KEY, {}).get("id") == comparison["id"]
        and config[COMPARISON_KEY].get("index") == comparison["index"]
        for config in later
    )


async def _what_changed(session: AsyncSession, run: EvaluationRun, evaluation: Evaluation) -> str | None:
    """What of the dataset or the scoring changed since this run started, or None when nothing did."""
    revision = (await session.exec(select(Dataset.revision).where(Dataset.id == run.dataset_id))).first()
    if evaluation.dataset_id != run.dataset_id or revision != run.dataset_revision:
        return "dataset"
    config = run.config or {}
    if evaluation.scorers != config.get("scorers") or evaluation.pass_threshold != config.get("pass_threshold"):
        return "scoring"
    return None


async def continue_comparison(run_id: UUID) -> UUID | None:
    """Start the next variant once this run ended; returns the new run's id, or None when nothing starts."""
    from langflow.services.evaluations.run_service import start_evaluation_run

    async with session_scope() as session:
        run = (await session.exec(select(EvaluationRun).where(EvaluationRun.id == run_id))).first()
        if run is None or run.status not in CONTINUE_AFTER or run.flow_version_id is None:
            return None
        step = next_step(run.config)
        if step is None:
            return None
        comparison, overrides = step
        if await _already_started(session, run, comparison):
            return None
        evaluation = (await session.exec(select(Evaluation).where(Evaluation.id == run.evaluation_id))).first()
        user = (await session.exec(select(User).where(User.id == run.user_id))).first()
        if evaluation is None or user is None:
            return None
        changed = await _what_changed(session, run, evaluation)
        if changed is not None:
            # Variants on other rows, or scored another way, would not be comparable.
            await logger.awarning(f"evals_comparison_stopped run_id={run_id} reason={changed}_changed")
            return None
        try:
            started = await start_evaluation_run(
                session, user, evaluation, run.flow_version_id, overrides, comparison=comparison
            )
        except EvalsError as exc:
            # The remaining variants show as not run; the reason goes to the log, not to a run row.
            await logger.awarning(
                f"evals_comparison_stopped run_id={run_id} next_index={comparison['index']} "
                f"error={type(exc).__name__}: {exc}"
            )
            return None
        await logger.ainfo(
            f"evals_comparison_next run_id={started.id} index={comparison['index']} of={len(comparison['variants'])}"
        )
        return started.id
