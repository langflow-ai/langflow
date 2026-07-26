"""Redacted run reports and Locust event listeners."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REDACT_KEY_FRAGMENTS = ("api_key", "password", "token", "secret", "authorization")


@dataclass
class RedactedRunReport:
    profile: str
    validity: dict[str, object]
    arrivals: dict[str, object]
    drain: dict[str, object]
    correctness_summary: dict[str, object]
    locust_stats_summary: dict[str, object]
    hashes: dict[str, str] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


def redact_secrets(obj: Any) -> Any:
    """Recursively strip values whose keys match sensitive fragments."""
    if isinstance(obj, dict):
        redacted: dict[str, Any] = {}
        for key, value in obj.items():
            key_lower = key.lower()
            if any(fragment in key_lower for fragment in _REDACT_KEY_FRAGMENTS):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = redact_secrets(value)
        return redacted
    if isinstance(obj, list):
        return [redact_secrets(item) for item in obj]
    return obj


def _locust_stats_summary(environment: Any) -> dict[str, object]:
    stats = environment.stats.total
    return {
        "num_requests": stats.num_requests,
        "num_failures": stats.num_failures,
        "fail_ratio": stats.fail_ratio,
        "p50_ms": stats.get_response_time_percentile(0.50) or 0,
        "p95_ms": stats.get_response_time_percentile(0.95) or 0,
        "p99_ms": stats.get_response_time_percentile(0.99) or 0,
        "current_rps": getattr(stats, "current_rps", 0.0),
    }


def write_report(
    report_dir: Path | str,
    profile: str,
    validity: dict[str, object],
    arrivals: dict[str, object],
    drain: dict[str, object],
    correctness_summary: dict[str, object],
    locust_stats_summary: dict[str, object],
    hashes: dict[str, str],
) -> Path:
    """Write a redacted JSON summary beside Locust CSV/HTML artifacts."""
    report = RedactedRunReport(
        profile=profile,
        validity=validity,
        arrivals=arrivals,
        drain=drain,
        correctness_summary=correctness_summary,
        locust_stats_summary=locust_stats_summary,
        hashes=hashes,
    )
    payload = redact_secrets(
        {
            "profile": report.profile,
            "generated_at": report.generated_at,
            "validity": report.validity,
            "arrivals": report.arrivals,
            "drain": report.drain,
            "correctness_summary": report.correctness_summary,
            "locust_stats_summary": report.locust_stats_summary,
            "hashes": report.hashes,
        }
    )
    out_dir = Path(report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "metrics_summary.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path


_LISTENER_STATE: dict[str, Any] = {
    "profile": "default",
    "validity": {},
    "arrivals": {},
    "drain": {},
    "correctness_summary": {},
    "hashes": {},
    "attached": False,
}


def set_report_context(
    *,
    profile: str | None = None,
    validity: dict[str, object] | None = None,
    arrivals: dict[str, object] | None = None,
    drain: dict[str, object] | None = None,
    correctness_summary: dict[str, object] | None = None,
    hashes: dict[str, str] | None = None,
) -> None:
    """Update context used when listeners write the JSON summary."""
    if profile is not None:
        _LISTENER_STATE["profile"] = profile
    if validity is not None:
        _LISTENER_STATE["validity"] = validity
    if arrivals is not None:
        _LISTENER_STATE["arrivals"] = arrivals
    if drain is not None:
        _LISTENER_STATE["drain"] = drain
    if correctness_summary is not None:
        _LISTENER_STATE["correctness_summary"] = correctness_summary
    if hashes is not None:
        _LISTENER_STATE["hashes"] = hashes


def finalize_reports(environment: Any) -> None:
    """Write the redacted metrics summary for the finished Locust run."""
    stats = getattr(getattr(environment, "stats", None), "total", None)
    if stats is None or stats.num_requests == 0:
        return
    report_dir = getattr(environment, "report_dir", None)
    if report_dir is None:
        run_context = getattr(environment, "run_context", None)
        report_dir = getattr(run_context, "report_dir", None) if run_context else None
    report_dir = report_dir or Path("reports")
    write_report(
        report_dir=report_dir,
        profile=str(_LISTENER_STATE["profile"]),
        validity=dict(_LISTENER_STATE["validity"]),
        arrivals=dict(_LISTENER_STATE["arrivals"]),
        drain=dict(_LISTENER_STATE["drain"]),
        correctness_summary=dict(_LISTENER_STATE["correctness_summary"]),
        locust_stats_summary=_locust_stats_summary(environment),
        hashes=dict(_LISTENER_STATE["hashes"]),
    )


def attach_listeners(environment: Any) -> None:
    """Register Locust listeners that emit a redacted JSON summary on test stop."""
    if _LISTENER_STATE["attached"]:
        return
    from locust import events

    events.test_stop.add_listener(lambda environment, **_kwargs: finalize_reports(environment))
    _LISTENER_STATE["attached"] = True
    run_context = getattr(environment, "run_context", None)
    if run_context is not None:
        set_report_context(profile=getattr(run_context.profile, "id", "default"))
        environment.report_dir = getattr(run_context, "report_dir", None)


def register_reporting_listeners(environment: Any) -> None:
    """Alias used by ``perf_locustfile`` on test start."""
    attach_listeners(environment)
