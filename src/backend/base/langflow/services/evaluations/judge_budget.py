"""The LLM judge's output-token budget for one run, shared by its concurrent rows."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JudgeRunBudget:
    """Output tokens each judge has written so far in this run.

    Rows already in progress when a judge reaches its budget still finish, so a run can go over by at most
    those rows' per-row limits.
    """

    used: dict[str, int] = field(default_factory=dict)

    def spent(self, judge: str, limit: int) -> bool:
        return self.used.get(judge, 0) >= limit

    def add(self, judge: str, output_tokens: int | None) -> None:
        if output_tokens:
            self.used[judge] = self.used.get(judge, 0) + output_tokens
