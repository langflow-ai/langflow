from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ScoreResult:
    """One scorer's verdict on one row; ``value`` is None when the scorer cannot judge the row."""

    value: float | None
    comment: str | None = None
    tokens: int | None = None
    cost: float | None = None
    output_tokens: int | None = None
    """Tokens the scorer's model wrote (the LLM judge), counted against the run's judge budget."""
    safety: dict[str, bool] | None = None
    """The LLM judge's safety checks on the answer, when the evaluation asked for them."""
    input_attack: str | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"value": self.value}
        if self.comment:
            payload["comment"] = self.comment
        if self.safety is not None:
            payload["safety"] = self.safety
            payload["input_attack"] = self.input_attack
        return payload


NOT_APPLICABLE_NO_EXPECTED = ScoreResult(value=None, comment="No expected output for this row")
