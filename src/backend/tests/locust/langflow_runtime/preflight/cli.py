"""CLI for performance-suite preflight checks."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from tests.locust.langflow_runtime.config.loader import FIXTURE_INDEX_PATH, load_profile, resolve_profile_path
from tests.locust.langflow_runtime.paths import state_dir, state_path_for
from tests.locust.langflow_runtime.preflight.dependencies import check_dependencies
from tests.locust.langflow_runtime.preflight.generator import check_generator_headroom
from tests.locust.langflow_runtime.preflight.health import check_auth, check_fixture_hashes, check_health
from tests.locust.langflow_runtime.preflight.protocols import run_protocol_checks
from tests.locust.langflow_runtime.provision import DEFAULT_ENV_ID


def _resolve_state_path(*, state: str | None, env_id: str | None) -> Path | None:
    if state:
        return Path(state)
    if env_id:
        return state_path_for(env_id)
    env_path = os.environ.get("PERF_STATE_PATH")
    if env_path:
        return Path(env_path)
    default_env = os.environ.get("PERF_ENV_ID") or DEFAULT_ENV_ID
    candidate = state_path_for(default_env)
    return candidate if candidate.exists() else None


def _load_state(path: Path | None) -> dict | None:
    if path is None:
        return None
    if not path.exists():
        print(f"WARN state file not found: {path}", file=sys.stderr)
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_fixture_index() -> dict | None:
    if not FIXTURE_INDEX_PATH.exists():
        return None
    return json.loads(FIXTURE_INDEX_PATH.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Langflow performance-suite preflight")
    parser.add_argument("--host", required=True, help="Langflow base URL")
    parser.add_argument("--state", default=None, help="Path to provision state JSON")
    parser.add_argument(
        "--env-id",
        default=None,
        help=f"Resolve state from {{PERF_DATA_DIR|/cache}}/state/{{env_id}}.json (default dir {state_dir()})",
    )
    parser.add_argument(
        "--profile",
        default="smoke/all_protocols",
        help="Profile id or path (default: smoke/all_protocols)",
    )
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    state_path = _resolve_state_path(state=args.state, env_id=args.env_id)
    state = _load_state(state_path)
    host = args.host.rstrip("/")
    if state and state.get("host") and args.host == "http://localhost:7860":
        host = str(state["host"]).rstrip("/")

    results = []
    results.append(check_health(host))
    if state and state.get("api_key"):
        results.append(check_auth(host, str(state["api_key"])))
    else:
        from tests.locust.langflow_runtime.preflight.health import CheckResult

        results.append(CheckResult(name="auth", ok=True, detail="skipped (no api_key)"))

    results.append(check_fixture_hashes(state, _load_fixture_index()))
    results.extend(
        check_dependencies(
            state,
            list(profile.protocols),
            flow_selectors=list(profile.flow_selectors),
        )
    )
    if state:
        results.extend(run_protocol_checks(host, state, list(profile.protocols)))
    results.append(check_generator_headroom(max_cpu_pct=float(profile.validity.max_generator_cpu_pct)))

    failed = False
    for result in results:
        status = "OK" if result.ok else "FAIL"
        if not result.ok:
            failed = True
        print(f"{status:4} {result.name}: {result.detail}")

    print(f"profile={resolve_profile_path(args.profile)}")
    if state_path:
        print(f"state={state_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
