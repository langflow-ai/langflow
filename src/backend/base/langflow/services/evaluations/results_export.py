from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

from langflow.services.evaluations.dataset_service import item_text
from langflow.utils.csv_safety import csv_safe_cell

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from langflow.services.database.models.evaluation import EvaluationResult

BASE_HEADERS = ("position", "input", "expected_output", "actual_output", "passed", "error")
METRIC_HEADERS = ("duration_ms", "tokens_flow", "tokens_judge", "cost_flow_usd", "cost_judge_usd", "trace_id")


def _score_cells(result: EvaluationResult, scorer_names: Sequence[str]) -> list[object]:
    cells: list[object] = []
    for name in scorer_names:
        entry = (result.scores or {}).get(name) or {}
        cells.extend([entry.get("value"), entry.get("comment")])
    return cells


def export_results(results: Sequence[EvaluationResult], scorer_names: Sequence[str]) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    score_headers = [csv_safe_cell(label) for name in scorer_names for label in (name, f"{name} comment")]
    writer.writerow([*BASE_HEADERS, *score_headers, *METRIC_HEADERS])
    yield "﻿" + buffer.getvalue()
    for result in results:
        buffer.seek(0)
        buffer.truncate()
        row = [
            result.position,
            item_text(result.input),
            item_text(result.expected_output),
            result.actual_output,
            result.passed,
            result.error,
            *_score_cells(result, scorer_names),
            result.duration_ms,
            result.tokens_flow,
            result.tokens_judge,
            result.cost_flow,
            result.cost_judge,
            result.trace_id,
        ]
        writer.writerow([csv_safe_cell(cell) for cell in row])
        yield buffer.getvalue()
