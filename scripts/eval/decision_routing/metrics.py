"""Release metrics from routing records: wrong routes, coverage, Else, errors, latency and cost.

Rates are over every case, so wrong-route rate, coverage, Else rate and error rate add up to 1 with
the correct-route rate. No numbers are assumed: prices and targets come from files a person supplies.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

# What each release target limits, and whether the measured value must stay at or below it, or above.
TARGETS = {
    "max_wrong_route_rate": ("wrong_route_rate", "max"),
    "min_coverage": ("coverage", "min"),
    "max_else_rate": ("else_rate", "max"),
    "max_error_rate": ("error_rate", "max"),
    "max_p95_latency_ms": ("p95_latency_ms", "max"),
    "max_cost_per_1000": ("cost_per_1000", "max"),
}


def percentile(values: list[float], fraction: float) -> float | None:
    """Nearest-rank percentile; None without values."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def _cost(records: list[dict], pricing: dict[str, dict] | None) -> float | None:
    """Dollars for these records from per-million-token prices keyed by target, or None if unpriced."""
    if not pricing:
        return None
    total = 0.0
    for record in records:
        price = pricing.get(record["target"].removeprefix("baseline "))
        if price is None or record["input_tokens"] is None:
            return None
        total += record["input_tokens"] * price.get("input_per_million", 0) / 1_000_000
        total += (record["output_tokens"] or 0) * price.get("output_per_million", 0) / 1_000_000
        total += price.get("per_request", 0)
    return total


def summarize(records: list[dict], pricing: dict[str, dict] | None = None) -> dict[str, Any]:
    """One target's metrics. ``records`` must all be for the same target."""
    n = len(records)
    outcomes = Counter(record["outcome"] for record in records)
    routed = outcomes["correct"] + outcomes["wrong"]
    expected_else = [r for r in records if r["expected"] == "Else"]
    latencies = [r["latency_ms"] for r in records if r["latency_ms"] is not None]
    cost = _cost(records, pricing)
    # None when no answer reported usage, so a missing count never reads as zero tokens.
    reported = [r for r in records if r["input_tokens"] is not None]
    tokens_in = sum(r["input_tokens"] for r in reported) if reported else None
    tokens_out = sum(r["output_tokens"] or 0 for r in reported) if reported else None
    confusion: dict[str, Counter] = {}
    for record in records:
        confusion.setdefault(record["expected"], Counter())[record["routed"]] += 1
    return {
        "target": records[0]["target"] if records else None,
        "cases": n,
        "correct": outcomes["correct"],
        "wrong": outcomes["wrong"],
        "else": outcomes["else"],
        "errors": outcomes["error"],
        "wrong_route_rate": _rate(outcomes["wrong"], n),
        "coverage": _rate(routed, n),
        "accuracy_when_routed": _rate(outcomes["correct"], routed),
        "else_rate": _rate(outcomes["else"], n),
        "error_rate": _rate(outcomes["error"], n),
        "errors_by_category": dict(Counter(r["error_category"] for r in records if r["outcome"] == "error")),
        # Messages no route should take: how many still went to a route.
        "should_be_else": len(expected_else),
        "false_accepts": sum(r["outcome"] in {"correct", "wrong"} for r in expected_else),
        "p50_latency_ms": percentile(latencies, 0.5),
        "p95_latency_ms": percentile(latencies, 0.95),
        "mean_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "cost": None if cost is None else round(cost, 6),
        "cost_per_1000": None if cost is None or not n else round(cost * 1000 / n, 4),
        "model_versions": dict(Counter(f"{r['model']} ({r['model_source'] or 'unknown'})" for r in records)),
        "confusion": {expected: dict(counts) for expected, counts in confusion.items()},
    }


def check_targets(summary: dict[str, Any], targets: dict[str, float] | None) -> list[dict[str, Any]]:
    """Each agreed target against the measured value; an unmeasured value never passes."""
    checks = []
    for name, limit in (targets or {}).items():
        if name not in TARGETS:
            msg = f"Unknown target {name!r}; use one of: {', '.join(TARGETS)}."
            raise ValueError(msg)
        metric, direction = TARGETS[name]
        actual = summary.get(metric)
        passed = actual is not None and (actual <= limit if direction == "max" else actual >= limit)
        checks.append({"target": name, "limit": limit, "metric": metric, "actual": actual, "passed": passed})
    return checks
