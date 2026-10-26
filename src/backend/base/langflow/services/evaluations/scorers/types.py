from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreResult:
    """One scorer's verdict on one row; ``value`` is None when the scorer cannot judge the row."""

    value: float | None
    comment: str | None = None
    tokens: int | None = None
    cost: float | None = None

    def to_json(self) -> dict[str, float | str | None]:
        payload: dict[str, float | str | None] = {"value": self.value}
        if self.comment:
            payload["comment"] = self.comment
        return payload


NOT_APPLICABLE_NO_EXPECTED = ScoreResult(value=None, comment="No expected output for this row")
