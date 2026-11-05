r"""Evaluate decision-model routing against a labelled suite, for the v1.14 release evidence.

Live runs bill every provider for every case, so the plan is printed first and a run needs --yes.

    # Check the suite and the harness offline, with fake answers:
    uv run python -m scripts.eval.decision_routing.run run \\
        scripts/eval/decision_routing/suites/support_ticket_routing.json --fake

    # Every mandatory provider, plus a language model baseline, against live APIs:
    uv run python -m scripts.eval.decision_routing.run run SUITE \\
        --target TypeSafe:jev-latest --target Perplexity:pplx-decider-latest --target OpenAI:gpt-6-luna \\
        --baseline OpenAI:gpt-4o-mini --pricing pricing.json --targets targets.json --yes

    # Recompute the report, sweep and target checks from a past run without new requests:
    uv run python -m scripts.eval.decision_routing.run report RUN_DIR --targets targets.json

Keys come from the environment (TYPESAFE_API_KEY, PERPLEXITY_API_KEY, OPENAI_API_KEY) exactly as a flow
reads them. They are never written to the output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from .dataset import Suite, SuiteError, load_suite
from .metrics import check_targets, summarize
from .report import render
from .runner import DECISION, LANGUAGE, FatalTargetError, Target, route_case

SWEEP = [round(0.5 + 0.05 * i, 2) for i in range(10)]


def _default_targets() -> list[Target]:
    from lfx.base.models.decision_constants import DECISION_MODELS_DETAILED

    return [Target(DECISION, row["provider"], row["name"]) for row in DECISION_MODELS_DETAILED]


def _read_json(path: str | None) -> dict | None:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def _run_target(suite: Suite, target: Target, concurrency: int) -> tuple[list[dict], str | None]:
    """Every case for one target, in suite order; stops the target at its first fatal error."""
    records: list[dict] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(route_case, suite, target, case) for case in suite.cases]
        for future in futures:
            try:
                records.append(future.result())
            except FatalTargetError as exc:
                for pending in futures:
                    pending.cancel()
                return records, str(exc)
    return records, None


def _sweep(suite: Suite, target: str, records: list[dict]) -> list[dict]:
    """Replay recorded answers at each minimum probability through the real router."""
    if suite.kind == "score":
        return []
    cases = {case.id: case for case in suite.cases}
    decision = Target.parse(target)
    rows = []
    for minimum in SWEEP:
        replayed = [
            route_case(suite, decision, cases[r["case_id"]], minimum_probability=minimum, recorded=r["result"])
            if r["result"]
            else r
            for r in records
        ]
        rows.append({"minimum": minimum, **summarize(replayed)})
    return rows


def _report(
    run: dict, suite: Suite, records: list[dict], stopped: dict, out: Path, pricing: dict | None, targets: dict | None
) -> bool:
    by_target: dict[str, list[dict]] = {}
    for record in records:
        by_target.setdefault(record["target"], []).append(record)
    summaries = [summarize(rows, pricing) for rows in by_target.values()]
    summaries += [{"target": target, "stopped": reason} for target, reason in stopped.items()]
    sweeps = {
        target: _sweep(suite, target, rows)
        for target, rows in by_target.items()
        if rows[0]["mode"] == DECISION and target not in stopped
    }
    checks = {s["target"]: check_targets(s, targets) for s in summaries if not s.get("stopped") and targets}
    run["targets"] = targets or {}
    (out / "summary.json").write_text(
        json.dumps({"run": run, "summaries": summaries, "sweeps": sweeps, "checks": checks}, indent=2) + "\n"
    )
    (out / "report.md").write_text(render(run, summaries, sweeps, checks), encoding="utf-8")
    print(f"Report: {out / 'report.md'}")
    return not stopped and all(row["passed"] for rows in checks.values() for row in rows)


def _run(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite)
    targets = [Target.parse(t) for t in args.target] or _default_targets()
    targets += [Target.parse(b, LANGUAGE) for b in args.baseline]
    requests = len(suite.cases) * len(targets)
    print(f"{suite.name}: {len(suite.cases)} cases x {len(targets)} targets = {requests} requests")
    for target in targets:
        print(f"  {target.label}")
    if args.fake and args.baseline:
        print("--fake answers decisions only; drop --baseline.", file=sys.stderr)
        return 2
    if not args.fake and requests > args.max_requests:
        print(f"That's more than --max-requests {args.max_requests}. Raise it to run.", file=sys.stderr)
        return 2
    if not args.fake and not args.yes:
        print("Live runs are billed by each provider. Add --yes to run.", file=sys.stderr)
        return 2
    if args.fake:
        from .fake import installed

        with installed(suite):
            return _execute(args, suite, targets)
    return _execute(args, suite, targets)


def _execute(args: argparse.Namespace, suite: Suite, targets: list[Target]) -> int:
    started = datetime.now(timezone.utc)
    out = Path(args.out) if args.out else Path(__file__).parent / "runs" / f"{suite.name}-{started:%Y%m%dT%H%M%SZ}"
    out.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    stopped: dict[str, str] = {}
    for target in targets:
        rows, reason = _run_target(suite, target, args.concurrency)
        records += rows
        if reason:
            stopped[target.label] = reason
            print(f"Stopped {target.label}: {reason}", file=sys.stderr)
    with (out / "records.jsonl").open("w", encoding="utf-8") as file:
        file.writelines(json.dumps(record) + "\n" for record in records)
    cases_file = Path(args.suite).parent / json.loads(Path(args.suite).read_text(encoding="utf-8"))["cases"]
    run = {
        "suite": suite.name,
        "suite_path": str(args.suite),
        "kind": suite.kind,
        "minimum_probability": suite.minimum_probability,
        "cases": len(suite.cases),
        "cases_sha256": hashlib.sha256(cases_file.read_bytes()).hexdigest(),
        "started_at": started.isoformat(timespec="seconds"),
        "fake": args.fake,
        "lfx_version": version("lfx"),
        "stopped": stopped,
    }
    (out / "run.json").write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    return 0 if _report(run, suite, records, stopped, out, _read_json(args.pricing), _read_json(args.targets)) else 1


def _rereport(args: argparse.Namespace) -> int:
    out = Path(args.run_dir)
    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    suite = load_suite(run["suite_path"])
    records = [json.loads(line) for line in (out / "records.jsonl").read_text(encoding="utf-8").splitlines() if line]
    passed = _report(
        run, suite, records, run.get("stopped", {}), out, _read_json(args.pricing), _read_json(args.targets)
    )
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Route every case and write records, a summary and a report.")
    run.add_argument("suite", help="Suite JSON file.")
    run.add_argument(
        "--target",
        action="append",
        default=[],
        help="Decision model as provider:model. Repeat. Default: every catalog decision model.",
    )
    run.add_argument(
        "--baseline",
        action="append",
        default=[],
        help="Language model as provider:model, routed in Language Model mode, as an existing flow would.",
    )
    run.add_argument(
        "--pricing",
        help='JSON: {"provider:model": {"input_per_million": 0.0, "output_per_million": 0.0, "per_request": 0.0}}.',
    )
    run.add_argument(
        "--targets", help='JSON release targets, such as {"max_wrong_route_rate": 0.02, "min_coverage": 0.8}.'
    )
    run.add_argument("--out", help="Output directory. Default: runs/<suite>-<UTC time> next to this script.")
    run.add_argument("--concurrency", type=int, default=4, help="Requests in flight per target. Default: 4.")
    run.add_argument(
        "--max-requests", type=int, default=500, help="Refuse a live run planning more requests. Default: 500."
    )
    run.add_argument("--fake", action="store_true", help="Offline fake answers: checks the suite and harness only.")
    run.add_argument("--yes", action="store_true", help="Confirm a live, billed run.")
    report = commands.add_parser("report", help="Rebuild the report from a run's records, without requests.")
    report.add_argument("run_dir")
    report.add_argument("--pricing")
    report.add_argument("--targets")
    args = parser.parse_args(argv)
    try:
        return _run(args) if args.command == "run" else _rereport(args)
    except (SuiteError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
