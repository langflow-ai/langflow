"""CLI for performance-suite preflight checks."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from tests.locust.langflow_runtime.config.loader import FIXTURE_INDEX_PATH, load_profile, resolve_profile_path
from tests.locust.langflow_runtime.config.selection import resolve_selection
from tests.locust.langflow_runtime.paths import state_dir, state_path_for
from tests.locust.langflow_runtime.preflight.dependencies import check_dependencies
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


def _resolve_profile(profile_ref: str | None, suite: str | None, external_apis: str | None):
    if suite:
        try:
            profile, path, _meta = resolve_selection(suite=suite, external_apis=external_apis)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        return profile, path
    if external_apis is not None:
        raise SystemExit("--external-apis is only valid with --suite natural")
    ref = profile_ref or "smoke/all_protocols"
    return load_profile(ref), resolve_profile_path(ref)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Langflow performance-suite preflight")
    parser.add_argument("--host", required=True, help="Langflow base URL")
    parser.add_argument("--state", default=None, help="Path to provision state JSON")
    parser.add_argument(
        "--env-id",
        default=None,
        help=f"Resolve state from {{PERF_DATA_DIR|/cache}}/state/{{env_id}}.json (default dir {state_dir()})",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--suite",
        default=None,
        help="Named suite to preflight, e.g. smoke",
    )
    selection.add_argument(
        "--profile",
        default=None,
        help="Committed profile id/path (advanced; default: smoke/all_protocols)",
    )
    parser.add_argument(
        "--external-apis",
        choices=("stubbed", "live"),
        help="Required with --suite natural",
    )
    args = parser.parse_args(argv)

    profile, profile_path = _resolve_profile(args.profile, args.suite, args.external_apis)
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
    failed = False
    for result in results:
        status = "OK" if result.ok else "FAIL"
        if not result.ok:
            failed = True
        print(f"{status:4} {result.name}: {result.detail}")

    print(f"profile={profile_path}")
    if state_path:
        print(f"state={state_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
