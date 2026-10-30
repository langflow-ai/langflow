"""Stop a run early when rows keep failing the same way (a retired model, a missing key, no quota)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from langflow.services.evaluations.scorers.llm_judge import UNREADABLE_VERDICT

if TYPE_CHECKING:
    from langflow.services.evaluations.row_scoring import RowScores

SCORER_FAILED_PREFIX = "Scorer failed: "
SIGNATURE_MAX_CHARS = 300
# Request ids, timestamps and counters differ between otherwise identical provider errors.
_VOLATILE = re.compile(
    r"\b(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|req_[A-Za-z0-9]+|[0-9a-f]{8,}|\d+)\b",
    re.IGNORECASE,
)
# Provider SDK errors embed a JSON-ish body; its "message" is the sentence a person can act on.
_PROVIDER_MESSAGE = re.compile(r"""['"]message['"]\s*:\s*(['"])(?P<message>.+?)\1""")


class RunAbortedError(Exception):
    """Raised by a row when the run must stop; the message is shown to the user."""


def failure_detail(error: str | None, scored: RowScores | None, scorers: list[dict[str, Any]]) -> str | None:
    """What went wrong in a row (the flow error, else a failed judge call); None when it went fine."""
    if error:
        return error
    if scored is None:
        return None
    for spec in scorers:
        if spec.get("type") != "llm_judge":
            continue
        entry = scored.scores.get(spec["name"])
        comment = (entry.comment if entry else None) or ""
        if comment.startswith(SCORER_FAILED_PREFIX) or comment == UNREADABLE_VERDICT:
            return comment
    return None


def readable_error(detail: str) -> str:
    match = _PROVIDER_MESSAGE.search(detail)
    return match.group("message") if match else detail


def _normalized_signature(text: str) -> str:
    return _VOLATILE.sub("#", text.strip())[:SIGNATURE_MAX_CHARS]


@dataclass
class FailureBreaker:
    """Trips after ``threshold`` consecutive rows fail with the same signature; 0 disables it."""

    threshold: int
    _last: str | None = None
    _streak: int = 0
    tripped_with: str | None = field(default=None)

    def record(self, detail: str | None) -> bool:
        """Count one finished row; True once the run should stop. Compares normalized text, keeps the raw one."""
        if self.threshold <= 0 or self.tripped_with is not None:
            return self.tripped_with is not None
        if detail is None:
            self._last, self._streak = None, 0
            return False
        signature = _normalized_signature(detail)
        self._streak = self._streak + 1 if signature == self._last else 1
        self._last = signature
        if self._streak >= self.threshold:
            self.tripped_with = readable_error(detail)[:SIGNATURE_MAX_CHARS]
            return True
        return False
