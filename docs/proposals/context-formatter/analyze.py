# ruff: noqa: INP001
"""Recompute descriptive metrics from sanitized historical observations; no network calls."""

import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, median


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[f"{row['cohort']}/{row['arm']}"].append(row)
    result = {}
    for name, attempts in sorted(groups.items()):
        usage = [request.get("usage") for row in attempts for request in row["requests"]]
        complete = not any(row["error"] for row in attempts) and all(
            u is not None and all(k in u for k in ("prompt_tokens", "completion_tokens", "total_tokens")) for u in usage
        )
        totals = {
            key: sum((u or {}).get(key, 0) or 0 for u in usage)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        }
        elapsed = sorted(row["total_ms"] for row in attempts)
        successes = sum(bool(row["success"]) for row in attempts)
        result[name] = {
            "attempts": len(attempts),
            "exact_successes": successes,
            "correct_decisions": sum(bool(row["answer_correct"]) for row in attempts),
            "usage_complete": complete,
            "mean_tokens": {key: value / len(attempts) for key, value in totals.items()},
            "tokens_per_success": totals["total_tokens"] / successes if successes else None,
            "median_ms": median(elapsed),
            "mean_ms": mean(elapsed),
            "median_success_ms": median(row["total_ms"] for row in attempts if row["success"]),
            "range_ms": [min(elapsed), max(elapsed)],
            "p95_ms": elapsed[math.ceil(0.95 * len(elapsed)) - 1],
            "model_requests": len(usage)
            + sum(bool(row["error"]) and not any(q["error"] for q in row["requests"]) for row in attempts),
            "mcp_calls": sum(row["mcp_calls"] for row in attempts),
            "errors": sum(bool(row["error"]) for row in attempts),
        }
    return result


if __name__ == "__main__":
    root = Path(__file__).parent
    observations = [json.loads(line) for line in (root / "observations.jsonl").read_text().splitlines()]
    print(json.dumps(summarize(observations), indent=2))  # noqa: T201
