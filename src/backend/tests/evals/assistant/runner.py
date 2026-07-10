"""Async eval runner for the Langflow Assistant flow builder.

Primary entry point (run from ``src/backend`` against a live backend):

    uv run --no-sync python -m tests.evals.assistant.runner --repeat 3

See README.md in this directory for the backend startup command and the
before/after gating rule for FLOW_BUILDER_PROMPT / classifier changes.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from tests.evals.assistant.harness import (
    Event,
    complete_data,
    duration_seconds,
    flow_updates,
    replay_final_flow,
    total_tokens,
)
from tests.evals.assistant.scenarios import SCENARIOS, Scenario, get_scenario

DEFAULT_BASE_URL = "http://127.0.0.1:7899"
DEFAULT_PROVIDER = "OpenAI"
DEFAULT_MODEL = "gpt-5.5"
# Hard transport cap per run so a hung stream cannot stall the whole suite.
_STREAM_TIMEOUT_MARGIN = 300.0


@dataclass
class RunResult:
    scenario: str
    run_index: int
    passed: bool
    failures: list[str] = field(default_factory=list)
    total_tokens: int | None = None
    duration_seconds: float | None = None
    verified: bool | None = None
    event_count: int = 0
    flow_update_count: int = 0


@dataclass
class ScenarioSummary:
    scenario: str
    description: str
    runs: int
    passes: int
    pass_rate: float
    pass_at_k: bool
    pass_all_k: bool
    avg_tokens: float | None
    avg_duration: float | None
    failure_reasons: list[str] = field(default_factory=list)


async def _get_token(client: httpx.AsyncClient) -> str:
    resp = await client.get("/api/v1/auto_login")
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not isinstance(token, str) or not token:
        msg = "auto_login returned no access_token — is LANGFLOW_AUTO_LOGIN=true on the backend?"
        raise RuntimeError(msg)
    return token


async def _create_flow(client: httpx.AsyncClient, headers: dict[str, str], name: str, data: dict[str, Any]) -> str:
    resp = await client.post("/api/v1/flows/", headers=headers, json={"name": name, "data": data})
    resp.raise_for_status()
    return str(resp.json()["id"])


async def _delete_flow(client: httpx.AsyncClient, headers: dict[str, str], flow_id: str) -> None:
    # Cleanup is best-effort; a leaked eval flow is harmless in the throwaway DB.
    with contextlib.suppress(httpx.HTTPError):
        await client.delete(f"/api/v1/flows/{flow_id}", headers=headers)


async def _stream_assist(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    flow_id: str,
    prompt: str,
    provider: str,
    model: str,
    session_id: str,
) -> list[Event]:
    payload = {
        "flow_id": flow_id,
        "input_value": prompt,
        "provider": provider,
        "model_name": model,
        "session_id": session_id,
    }
    events: list[Event] = []
    stream_headers = {**headers, "Accept": "text/event-stream"}
    async with client.stream("POST", "/api/v1/agentic/assist/stream", headers=stream_headers, json=payload) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            try:
                event = json.loads(line[len("data: ") :])
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
    return events


async def run_scenario_once(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    scenario: Scenario,
    run_index: int,
    *,
    provider: str,
    model: str,
) -> RunResult:
    seed = scenario.seed_flow() if scenario.seed_flow else {"nodes": [], "edges": []}
    flow_name = f"eval-{scenario.name}-{uuid.uuid4().hex[:8]}"
    flow_id = await _create_flow(client, headers, flow_name, seed)
    session_id = f"agentic_eval_{scenario.name}_{run_index}_{uuid.uuid4().hex[:8]}"
    try:
        events = await asyncio.wait_for(
            _stream_assist(
                client,
                headers,
                flow_id=flow_id,
                prompt=scenario.prompt,
                provider=provider,
                model=model,
                session_id=session_id,
            ),
            timeout=scenario.duration_ceiling + _STREAM_TIMEOUT_MARGIN,
        )
    except (httpx.HTTPError, TimeoutError) as exc:
        return RunResult(
            scenario=scenario.name,
            run_index=run_index,
            passed=False,
            failures=[f"transport failure: {type(exc).__name__}: {exc}"],
        )
    finally:
        await _delete_flow(client, headers, flow_id)

    final_flow = replay_final_flow(seed, events)
    failures = scenario.evaluate(events, final_flow)
    data = complete_data(events) or {}
    verified = data.get("verified") if isinstance(data.get("verified"), bool) else None
    return RunResult(
        scenario=scenario.name,
        run_index=run_index,
        passed=not failures,
        failures=failures,
        total_tokens=total_tokens(events),
        duration_seconds=duration_seconds(events),
        verified=verified,
        event_count=len(events),
        flow_update_count=len(flow_updates(events)),
    )


def summarize(scenario: Scenario, results: list[RunResult]) -> ScenarioSummary:
    passes = sum(1 for r in results if r.passed)
    tokens = [r.total_tokens for r in results if r.total_tokens is not None]
    durations = [r.duration_seconds for r in results if r.duration_seconds is not None]
    reasons: list[str] = []
    for result in results:
        reasons.extend(result.failures)
    return ScenarioSummary(
        scenario=scenario.name,
        description=scenario.description,
        runs=len(results),
        passes=passes,
        pass_rate=passes / len(results) if results else 0.0,
        pass_at_k=passes > 0,
        pass_all_k=passes == len(results),
        avg_tokens=sum(tokens) / len(tokens) if tokens else None,
        avg_duration=sum(durations) / len(durations) if durations else None,
        failure_reasons=reasons,
    )


def _print_summary(summaries: list[ScenarioSummary]) -> None:
    header = f"{'scenario':<26} {'pass':>9} {'rate':>6} {'avg tokens':>11} {'avg secs':>9}  first failure"
    print(header)
    print("-" * len(header))
    for s in summaries:
        tokens = f"{s.avg_tokens:,.0f}" if s.avg_tokens is not None else "-"
        secs = f"{s.avg_duration:.1f}" if s.avg_duration is not None else "-"
        first = s.failure_reasons[0][:70] if s.failure_reasons else ""
        print(f"{s.scenario:<26} {s.passes:>4}/{s.runs:<4} {s.pass_rate:>6.0%} {tokens:>11} {secs:>9}  {first}")
    total_runs = sum(s.runs for s in summaries)
    total_passes = sum(s.passes for s in summaries)
    print("-" * len(header))
    capable = sum(1 for s in summaries if s.pass_at_k)
    print(f"overall: {total_passes}/{total_runs} runs passed; {capable}/{len(summaries)} scenarios pass@k")


async def run_suite(
    *,
    base_url: str,
    scenarios: list[Scenario],
    repeat: int,
    provider: str,
    model: str,
    report_path: Path,
) -> int:
    timeout = httpx.Timeout(30.0, read=None)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        token = await _get_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        all_results: dict[str, list[RunResult]] = {}
        for scenario in scenarios:
            all_results[scenario.name] = []
            for run_index in range(repeat):
                print(f"[{scenario.name}] run {run_index + 1}/{repeat} ...", flush=True)
                result = await run_scenario_once(client, headers, scenario, run_index, provider=provider, model=model)
                status = "PASS" if result.passed else f"FAIL {result.failures}"
                print(f"[{scenario.name}] run {run_index + 1}/{repeat}: {status}", flush=True)
                all_results[scenario.name].append(result)

    summaries = [summarize(scenario, all_results[scenario.name]) for scenario in scenarios]
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "provider": provider,
        "model": model,
        "repeat": repeat,
        "scenarios": [
            {**asdict(summary), "runs_detail": [asdict(r) for r in all_results[summary.scenario]]}
            for summary in summaries
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nreport written to {report_path}\n")
    _print_summary(summaries)
    # Gate on capability (pass@k): a scenario with ZERO passing runs is a regression.
    return 0 if all(s.pass_at_k for s in summaries) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Langflow Assistant eval suite against a live backend.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("LANGFLOW_EVAL_BASE_URL", DEFAULT_BASE_URL),
        help="Backend base URL (or set LANGFLOW_EVAL_BASE_URL).",
    )
    parser.add_argument("--repeat", type=int, default=1, help="Runs per scenario (pass-rate estimation).")
    parser.add_argument(
        "--scenario",
        action="append",
        default=None,
        help="Run only this scenario (repeatable). Default: all scenarios.",
    )
    parser.add_argument("--provider", default=os.environ.get("LANGFLOW_EVAL_PROVIDER", DEFAULT_PROVIDER))
    parser.add_argument("--model", default=os.environ.get("LANGFLOW_EVAL_MODEL", DEFAULT_MODEL))
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(os.environ.get("LANGFLOW_EVAL_REPORT", "assistant_eval_report.json")),
        help="Output JSON report path.",
    )
    parser.add_argument("--list", action="store_true", help="List scenarios and exit.")
    args = parser.parse_args(argv)

    if args.list:
        for scenario in SCENARIOS:
            print(f"{scenario.name:<26} {scenario.description}")
        return 0

    scenarios = [get_scenario(name) for name in args.scenario] if args.scenario else list(SCENARIOS)
    return asyncio.run(
        run_suite(
            base_url=args.base_url,
            scenarios=scenarios,
            repeat=max(1, args.repeat),
            provider=args.provider,
            model=args.model,
            report_path=args.report,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
