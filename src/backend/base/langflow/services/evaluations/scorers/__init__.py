from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from langflow.services.evaluations.scorers.llm_judge import score_llm_judge
from langflow.services.evaluations.scorers.text import score_contains, score_exact_match, score_similarity
from langflow.services.evaluations.scorers.types import ScoreResult

if TYPE_CHECKING:
    from uuid import UUID

_TEXT_SCORERS = {
    "exact_match": score_exact_match,
    "contains": score_contains,
    "similarity": score_similarity,
}


async def run_scorer(
    spec: dict[str, Any],
    *,
    question: str,
    actual: str,
    expected: str | None,
    user_id: UUID,
    judge_max_output_tokens: int,
) -> ScoreResult:
    scorer_type = spec["type"]
    config = spec.get("config") or {}
    if scorer_type == "llm_judge":
        return await score_llm_judge(
            question=question,
            actual=actual,
            expected=expected,
            config=config,
            user_id=user_id,
            max_output_tokens=judge_max_output_tokens,
        )
    text_scorer = _TEXT_SCORERS.get(scorer_type)
    if text_scorer is None:
        return ScoreResult(value=None, comment=f"Unknown scorer type {scorer_type!r}")
    # Similarity is quadratic in pure Python: keep it off the event loop that serves the API.
    return await asyncio.to_thread(text_scorer, actual, expected, config)


__all__ = ["ScoreResult", "run_scorer"]
