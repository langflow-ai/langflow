"""Offline answers for a smoke run: checks the harness and the suite, never a provider.

Each case gets a deterministic distribution from a hash of its text: mostly confident and right,
sometimes unsure, sometimes wrong. The numbers it produces mean nothing about any model.
"""

from __future__ import annotations

import contextlib
import hashlib
from typing import TYPE_CHECKING

from lfx.base.models.decisions.schema import DecisionResult
from lfx.components.llm_operations import llm_conditional_router

from .dataset import ELSE, Suite

if TYPE_CHECKING:
    from collections.abc import Iterator


# About one case in ten is answered confidently but wrongly.
WRONG_SHARE = 0.1


def _roll(text: str) -> float:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF


@contextlib.contextmanager
def installed(suite: Suite) -> Iterator[None]:
    """Answer every decision the router asks with a fake result built from the case's label, then restore."""
    expected = {case.text: case.expected for case in suite.cases}

    def evaluate(request, *, model, **_kwargs) -> DecisionResult:
        roll = _roll(request.context)
        label = expected[request.context]
        common = {"kind": request.kind, "provider": model[0]["provider"], "model": f"{model[0]['name']}-fake"}
        if request.kind == "boolean":
            yes = {"Yes": 0.9, "No": 0.1}.get(label, 0.55)
            return DecisionResult(**common, probability_true=round(1 - yes if roll < WRONG_SHARE else yes, 2))
        candidates = request.options or request.levels
        names = [c.label for c in candidates]
        top = names.index(label) if label != ELSE else int(roll * len(names)) % len(names)
        if roll < WRONG_SHARE:
            top = (top + 1) % len(names)
        share = 0.85 if label != ELSE else 0.4
        rest = round((1 - share) / (len(names) - 1), 6)
        probabilities = {
            c.id: (round(1 - rest * (len(names) - 1), 6) if i == top else rest) for i, c in enumerate(candidates)
        }
        score = sum(i * p for i, p in enumerate(probabilities.values())) if request.kind == "score" else None
        return DecisionResult(**common, probabilities=probabilities, score=score)

    original = llm_conditional_router.evaluate_decision
    llm_conditional_router.evaluate_decision = evaluate
    try:
        yield
    finally:
        llm_conditional_router.evaluate_decision = original
