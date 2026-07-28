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
from tests.locust.langflow_runtime.config.selection import (
    STRESS_AXES,
    load_suites_catalog,
    resolve_selection,
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


def _build_locust_command(context_host: str, report_dir: Path) -> list[str]:
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
    print("axes:")
    for axis in STRESS_AXES:
        print(f"  {axis}")
    print("suites:")
    for name, entry in sorted(load_suites_catalog().items()):
        desc = entry.get("description", "")
        print(f"  {name}: {desc}")
    print("committed profiles:")
    for path in list_profiles():
        print(f"  {_profile_ref(path)}")
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


def _add_selection_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        "--axes",
        help="Comma-separated stress axes (1..N), e.g. chat_db or chat_db,cpu_graph",
    )
    group.add_argument(
        "--suite",
        help="Named suite: duet ids, tutti, smoke, or natural",
    )
    parser.add_argument(
        "--external-apis",
        choices=("stubbed", "live"),
        help="Required with --suite natural",
    )
    parser.add_argument("--host")
    parser.add_argument("--env-id")
    parser.add_argument("--run-id")
    parser.add_argument("--seed", type=int, default=0, help="Deterministic workload seed (default: 0)")
    # Escape hatch for debugging committed profiles (not part of Make sugar).
    parser.add_argument(
        "--profile",
        dest="profile_opt",
        help=argparse.SUPPRESS,
    )


def _resolve_context(args: argparse.Namespace):
    from tests.locust.langflow_runtime.config.context import build_run_context

    # Hidden --profile escape hatch for validate/debug of committed JSON.
    profile_ref = getattr(args, "profile_opt", None)
    axes = getattr(args, "axes", None)
    suite = getattr(args, "suite", None)
    external_apis = getattr(args, "external_apis", None)
    selection_meta: dict = {}
    if profile_ref:
        if axes or suite:
            msg = "use either --profile or --axes/--suite, not both"
            raise SystemExit(msg)
        if external_apis is not None:
            raise SystemExit("--external-apis is only valid with --suite natural")
        profile = load_profile(profile_ref)
        profile_path = resolve_profile_path(profile_ref)
        selection_meta = {"kind": "profile", "profile": profile_ref}
    else:
        if bool(axes) == bool(suite):
            msg = "exactly one of --axes or --suite is required"
            raise SystemExit(msg)
        try:
            profile, profile_path, selection_meta = resolve_selection(
                axes=axes,
                suite=suite,
                external_apis=external_apis,
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

    run_id = args.run_id or uuid4().hex[:12]
    report_dir = reports_dir() / run_id
    state_path = _default_state_path(args.env_id)
    if args.env_id and (state_path is None or not state_path.exists()):
        msg = f"provision state missing for --env-id {args.env_id!r} (expected {state_path})"
        raise SystemExit(msg)
    provision_state = _load_state(state_path)
    selection = selection_meta.get("selection", selection_meta)
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
            "selection": selection,
            "external_apis": getattr(profile, "external_apis", None),
            "movement_role": getattr(profile, "movement_role", None),
            "seed": args.seed,
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
    command = _build_locust_command(context.host, context.report_dir)
    env = _runtime_env(context)
    print(" ".join(command))
    for key in sorted(env):
        if key.startswith("PERF_") or key in {"LANGFLOW_HOST"}:
            print(f"{key}={_redact_env_value(key, env[key])}")
    return 0


def _runtime_env(context) -> dict[str, str]:
    import json

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
    # Forward safe selection/reproducibility metadata into the Locust process.
    context_payload = {
        "selection": context.overrides.get("selection"),
        "profile_sha256": context.overrides.get("profile_sha256"),
        "flow_selectors": context.overrides.get("flow_selectors"),
        "dataset_selectors": context.overrides.get("dataset_selectors"),
        "fixture_hashes": context.overrides.get("fixture_hashes"),
        "external_apis": context.overrides.get("external_apis"),
        "movement_role": context.overrides.get("movement_role"),
        "seed": context.overrides.get("seed"),
    }
    env["PERF_RUN_CONTEXT_JSON"] = json.dumps(context_payload, sort_keys=True)
    return env


def _cmd_run(args: argparse.Namespace) -> int:
    context = _resolve_context(args)
    from tests.locust.langflow_runtime.preflight.dependencies import check_dependencies

    dependency_results = check_dependencies(
        context.provision_state,
        list(context.profile.protocols),
        flow_selectors=list(context.profile.flow_selectors),
    )
    failures = [result for result in dependency_results if not result.ok]
    if failures:
        detail = "\n".join(f"  - {result.name}: {result.detail}" for result in failures)
        raise SystemExit(f"preflight dependency check failed:\n{detail}")
    context.report_dir.mkdir(parents=True, exist_ok=True)
    command = _build_locust_command(context.host, context.report_dir)
    env = _runtime_env(context)
    completed = subprocess.run(command, cwd=BACKEND_ROOT, env=env, check=False)
    return int(completed.returncode)


def _cmd_emit_schema(_args: argparse.Namespace) -> int:
    path = emit_schema()
    print(path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Langflow performance suite runner",
        epilog=(
            "Run directly with --axes/--suite, for example: "
            "python -m tests.locust.langflow_runtime.run --axes chat_db --host HOST --env-id ENV_ID"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List axes, suites, and committed profiles")
    list_parser.set_defaults(func=_cmd_list)

    validate_parser = subparsers.add_parser("validate", help="Validate one or all committed profiles")
    validate_parser.add_argument("profiles", nargs="*", help="Profile id/path (default: all supported profiles)")
    validate_parser.set_defaults(func=_cmd_validate)

    dry_run_parser = subparsers.add_parser("dry-run", help="Print resolved Locust command")
    _add_selection_args(dry_run_parser)
    dry_run_parser.set_defaults(func=_cmd_dry_run)

    run_parser = subparsers.add_parser("run", help="Execute exactly one movement")
    _add_selection_args(run_parser)
    run_parser.set_defaults(func=_cmd_run)

    schema_parser = subparsers.add_parser("emit-schema", help="Write profiles/schema.json")
    schema_parser.set_defaults(func=_cmd_emit_schema)

    return parser


def _normalize_argv(argv: list[str]) -> list[str]:
    """Accept the documented direct selection form while retaining subcommands."""
    commands = {"list", "validate", "dry-run", "run", "emit-schema"}
    has_selection = any(
        arg in {"--axes", "--suite", "--profile"} or arg.startswith(("--axes=", "--suite=", "--profile="))
        for arg in argv
    )
    if argv and argv[0] not in commands and has_selection:
        return ["run", *argv]
    return argv


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(_normalize_argv(raw_argv))
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
