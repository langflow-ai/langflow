"""A Markdown report a reviewer can read and paste into the release ticket."""

from __future__ import annotations

from typing import Any


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _num(value: float | None, unit: str = "") -> str:
    return "n/a" if value is None else f"{value:,.1f}{unit}" if isinstance(value, float) else f"{value:,}{unit}"


def _money(value: float | None) -> str:
    return "unpriced" if value is None else f"${value:,.4f}"


def render(run: dict[str, Any], summaries: list[dict], sweeps: dict[str, list[dict]], checks: dict[str, list]) -> str:
    lines = [
        f"# Decision routing evaluation: {run['suite']}",
        "",
        f"- Run: {run['started_at']} ({'offline fake answers, not evidence' if run['fake'] else 'live providers'})",
        f"- Suite: `{run['suite_path']}`, {run['cases']} cases, kind **{run['kind']}**, "
        f"minimum probability {run['minimum_probability']}, cases SHA-256 `{run['cases_sha256'][:12]}`",
        f"- lfx {run['lfx_version']}",
        "",
        "## Results",
        "",
        "| Target | Model versions | Wrong route | Coverage | Else | Errors | Accuracy when routed | "
        "p50 / p95 latency | Tokens in / out | Cost per 1,000 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        if s.get("stopped"):
            lines.append(f"| {s['target']} | stopped: {s['stopped']} | | | | | | | | |")
            continue
        versions = ", ".join(f"`{v}`" for v in s["model_versions"])
        latency = f"{_num(s['p50_latency_ms'], ' ms')} / {_num(s['p95_latency_ms'], ' ms')}"
        lines.append(
            f"| {s['target']} | {versions} | {_pct(s['wrong_route_rate'])} | {_pct(s['coverage'])} | "
            f"{_pct(s['else_rate'])} | {_pct(s['error_rate'])} | {_pct(s['accuracy_when_routed'])} | {latency} | "
            f"{_num(s['input_tokens'])} / {_num(s['output_tokens'])} | {_money(s['cost_per_1000'])} |"
        )
    lines += ["", "Correct + wrong route + Else + errors = 100% of cases. Coverage is correct + wrong route.", ""]
    for s in summaries:
        if s.get("stopped"):
            continue
        lines += [f"### {s['target']}", ""]
        if s["errors_by_category"]:
            lines.append("Errors: " + ", ".join(f"{k} {v}" for k, v in s["errors_by_category"].items()))
        if s["should_be_else"]:
            lines.append(f"Cases labelled Else: {s['should_be_else']}, of which {s['false_accepts']} went to a route.")
        outcomes = sorted({routed for counts in s["confusion"].values() for routed in counts})
        lines += ["", "| Expected \\ Routed | " + " | ".join(outcomes) + " |", "|---|" + "---|" * len(outcomes)]
        for expected, counts in sorted(s["confusion"].items()):
            lines.append(f"| {expected} | " + " | ".join(str(counts.get(o, 0)) for o in outcomes) + " |")
        if s["target"] in sweeps:
            lines += [
                "",
                "Minimum probability sweep (replayed from these answers, no new requests):",
                "",
                "| Minimum | Wrong route | Coverage | Else |",
                "|---|---|---|---|",
            ]
            lines += [
                f"| {row['minimum']:.2f} | {_pct(row['wrong_route_rate'])} | {_pct(row['coverage'])} | "
                f"{_pct(row['else_rate'])} |"
                for row in sweeps[s["target"]]
            ]
        lines.append("")
    lines += ["## Release targets", ""]
    if not run["targets"]:
        lines.append(
            "No targets were given. Numerical release targets are set with the dataset owner; until then "
            "these results are measurements, not a pass or fail."
        )
    else:
        lines += ["| Target | Check | Limit | Actual | Result |", "|---|---|---|---|---|"]
        for target, rows in checks.items():
            lines += [
                f"| {target} | {row['target']} | {row['limit']} | {row['actual']} | "
                f"{'pass' if row['passed'] else 'FAIL'} |"
                for row in rows
            ]
    return "\n".join(lines) + "\n"
