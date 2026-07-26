"""CLI for the Langflow performance suite."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from tests.locust.langflow_runtime.config.loader import (
    emit_schema,
    list_profiles,
    load_profile,
    resolve_profile_path,
    validate_all_profiles,
    validate_profile,
)
from tests.locust.langflow_runtime.paths import reports_dir, state_path_for

# Suite package root (…/tests/locust/langflow_runtime)
SUITE_ROOT = Path(__file__).resolve().parent
# Locust tree root (…/tests/locust) — legacy harness siblings live here
LOCUST_ROOT = SUITE_ROOT.parent
# Backend package root (…/src/backend) — Locust is invoked with cwd here
BACKEND_ROOT = SUITE_ROOT.parents[2]
PERF_LOCUSTFILE = SUITE_ROOT / "perf_locustfile.py"


def _profile_ref(path: Path) -> str:
    profiles_dir = SUITE_ROOT / "profiles"
    return str(path.relative_to(profiles_dir))


def _build_locust_command(context_host: str, report_dir: Path, profile_path: Path) -> list[str]:
    csv_prefix = str(report_dir / "locust")
    html_path = str(report_dir / "report.html")
    return [
        "locust",
        "-f",
        str(PERF_LOCUSTFILE.relative_to(BACKEND_ROOT)),
        "--host",
        context_host,
        "--headless",
        "--csv",
        csv_prefix,
        "--html",
        html_path,
    ]


def _cmd_list(_args: argparse.Namespace) -> int:
    for path in list_profiles():
        print(_profile_ref(path))
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    if args.profiles:
        failed = False
        for profile_id in args.profiles:
            errors = validate_profile(profile_id)
            if errors:
                failed = True
                print(f"FAIL {profile_id}:")
                for error in errors:
                    print(f"  - {error}")
            else:
                print(f"OK   {profile_id}")
        return 1 if failed else 0

    results = validate_all_profiles()
    failed = False
    for profile_id, errors in sorted(results.items()):
        if errors:
            failed = True
            print(f"FAIL {profile_id}:")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"OK   {profile_id}")
    return 1 if failed else 0


def _default_state_path(env_id: str | None) -> Path | None:
    env_path = os.environ.get("PERF_STATE_PATH")
    if env_path:
        return Path(env_path).expanduser()
    if env_id:
        return state_path_for(env_id)
    return None


def _load_state(path: Path | None) -> dict | None:
    if path is None:
        return None
    if not path.exists():
        return None
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _profile_content_hash(profile_path: Path) -> str:
    import hashlib

    return hashlib.sha256(profile_path.read_bytes()).hexdigest()


def _resolve_context(args: argparse.Namespace):
    from tests.locust.langflow_runtime.config.context import build_run_context

    profile_ref = getattr(args, "profile", None) or getattr(args, "profile_opt", None)
    if not profile_ref:
        msg = "profile is required"
        raise SystemExit(msg)
    profile = load_profile(profile_ref)
    profile_path = resolve_profile_path(profile_ref)
    run_id = args.run_id or uuid4().hex[:12]
    report_dir = reports_dir() / run_id
    state_path = _default_state_path(args.env_id)
    if args.env_id and (state_path is None or not state_path.exists()):
        msg = f"provision state missing for --env-id {args.env_id!r} (expected {state_path})"
        raise SystemExit(msg)
    provision_state = _load_state(state_path)
    return build_run_context(
        profile,
        host=args.host,
        run_id=run_id,
        report_dir=report_dir,
        env_id=args.env_id,
        provision_state=provision_state,
        overrides={
            "profile_path": str(profile_path),
            "profile_sha256": _profile_content_hash(profile_path),
            "state_path": str(state_path) if state_path else None,
            "flow_selectors": list(profile.flow_selectors),
            "dataset_selectors": list(profile.dataset_selectors),
            "fixture_hashes": (provision_state or {}).get("fixture_hashes"),
        },
    )


SECRET_ENV_KEYS = frozenset(
    {
        "PERF_PASSWORD",
        "PERF_SUPERUSER_PASSWORD",
        "PERF_API_KEY",
        "PERF_TOKEN",
        "PERF_ACCESS_TOKEN",
        "LANGFLOW_SUPERUSER_PASSWORD",
        "LANGFLOW_API_KEY",
    }
)


def _redact_env_value(key: str, value: str) -> str:
    upper = key.upper()
    if upper in SECRET_ENV_KEYS or any(token in upper for token in ("PASSWORD", "SECRET", "TOKEN", "API_KEY")):
        return "***"
    return value


def _cmd_dry_run(args: argparse.Namespace) -> int:
    context = _resolve_context(args)
    command = _build_locust_command(context.host, context.report_dir, Path(context.overrides["profile_path"]))
    env = _runtime_env(context)
    print(" ".join(command))
    for key in sorted(env):
        if key.startswith("PERF_") or key in {"LANGFLOW_HOST"}:
            print(f"{key}={_redact_env_value(key, env[key])}")
    return 0


def _runtime_env(context) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(BACKEND_ROOT), env["PYTHONPATH"]] if env.get("PYTHONPATH") else [str(BACKEND_ROOT)]
    )
    env["PERF_PROFILE_PATH"] = str(context.overrides["profile_path"])
    env["PERF_HOST"] = context.host
    env["LANGFLOW_HOST"] = context.host
    env["PERF_RUN_ID"] = context.run_id
    env["PERF_REPORT_DIR"] = str(context.report_dir)
    if context.env_id:
        env["PERF_ENV_ID"] = context.env_id
    if context.state_path:
        env["PERF_STATE_PATH"] = context.state_path
    return env


def _cmd_run(args: argparse.Namespace) -> int:
    context = _resolve_context(args)
    context.report_dir.mkdir(parents=True, exist_ok=True)
    command = _build_locust_command(context.host, context.report_dir, Path(context.overrides["profile_path"]))
    env = _runtime_env(context)
    completed = subprocess.run(command, cwd=BACKEND_ROOT, env=env, check=False)
    return int(completed.returncode)


def _cmd_emit_schema(_args: argparse.Namespace) -> int:
    path = emit_schema()
    print(path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Langflow performance suite runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List available movement profiles")
    list_parser.set_defaults(func=_cmd_list)

    validate_parser = subparsers.add_parser("validate", help="Validate one or all profiles")
    validate_parser.add_argument("profiles", nargs="*", help="Profile id/path (default: all)")
    validate_parser.set_defaults(func=_cmd_validate)

    dry_run_parser = subparsers.add_parser("dry-run", help="Print resolved Locust command")
    dry_run_parser.add_argument("profile", nargs="?", help="Exactly one profile id/path")
    dry_run_parser.add_argument("--profile", dest="profile_opt", help="Alias for positional profile")
    dry_run_parser.add_argument("--host")
    dry_run_parser.add_argument("--env-id")
    dry_run_parser.add_argument("--run-id")
    dry_run_parser.set_defaults(func=_cmd_dry_run)

    run_parser = subparsers.add_parser("run", help="Execute exactly one profile")
    run_parser.add_argument("profile", nargs="?", help="Exactly one profile id/path")
    run_parser.add_argument("--profile", dest="profile_opt", help="Alias for positional profile")
    run_parser.add_argument("--host")
    run_parser.add_argument("--env-id")
    run_parser.add_argument("--run-id")
    run_parser.set_defaults(func=_cmd_run)

    schema_parser = subparsers.add_parser("emit-schema", help="Write profiles/schema.json")
    schema_parser.set_defaults(func=_cmd_emit_schema)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
