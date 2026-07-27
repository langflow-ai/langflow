"""CLI for idempotent performance-suite provisioning.

Usage (from ``src/backend``)::

    PYTHONPATH=. uv run python -m tests.locust.langflow_runtime.provision.cli plan --host ... --env-id ...
    PYTHONPATH=. uv run python -m tests.locust.langflow_runtime.provision.cli apply --host ... --env-id ...
    PYTHONPATH=. uv run python -m tests.locust.langflow_runtime.provision.cli validate --env-id ...
    PYTHONPATH=. uv run python -m tests.locust.langflow_runtime.provision.cli teardown --env-id ...
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from tests.locust.langflow_runtime.datasets.storage_payload import bounded_payload_text
from tests.locust.langflow_runtime.provision import DEFAULT_ENV_ID, SMOKE_FLOW_IDS
from tests.locust.langflow_runtime.provision.api import ProvisionHttp
from tests.locust.langflow_runtime.provision.api_keys import create_suite_api_key
from tests.locust.langflow_runtime.provision.chat_seed import seed_chat_history
from tests.locust.langflow_runtime.provision.flows import (
    fixture_index_hash,
    index_by_id,
    load_fixture_index,
    provision_flows,
    resolve_flow_ids,
    tagged_endpoint_name,
)
from tests.locust.langflow_runtime.provision.hitl import validate_hitl_lifecycle
from tests.locust.langflow_runtime.provision.kbs import needs_kb, provision_kb
from tests.locust.langflow_runtime.provision.mcp import configure_mcp_for_state, validate_mcp_tools_listable
from tests.locust.langflow_runtime.provision.projects import project_name
from tests.locust.langflow_runtime.provision.state import (
    load_state,
    new_state,
    redact_state_for_log,
    register_resource,
    save_state,
    state_path_for,
)
from tests.locust.langflow_runtime.provision.teardown import teardown_state
from tests.locust.langflow_runtime.provision.users import authenticate, ensure_suite_user_pool
from tests.locust.langflow_runtime.provision.webhooks import (
    provision_webhook_copies,
    validate_webhook_subscribe_before_post,
    webhook_copy_count,
)


def _default_host() -> str:
    return os.environ.get("LANGFLOW_HOST") or os.environ.get("PERF_HOST") or "http://localhost:7860"


def _default_env_id() -> str:
    return os.environ.get("PERF_ENV_ID") or DEFAULT_ENV_ID


def _split_flows(raw: str | None) -> list[str] | None:
    if raw is None or raw.strip() == "":
        return None
    return [part.strip() for part in raw.split(",") if part.strip()]


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default=None, help="Langflow base URL (LANGFLOW_HOST / PERF_HOST)")
    parser.add_argument("--env-id", default=None, help="Suite environment id (PERF_ENV_ID / perf-local)")
    parser.add_argument(
        "--mode",
        choices=("superuser-pool", "existing-user"),
        default="superuser-pool",
        help="Auth mode",
    )
    parser.add_argument("--username", default=None, help="Username for existing-user / override")
    parser.add_argument("--password", default=None, help="Password for existing-user / override")
    parser.add_argument(
        "--flows",
        default=None,
        help=(
            "Comma-separated fixture ids, or 'smoke' default, 'v1' (all non-deferred), "
            f"or 'all'. Default: smoke set ({', '.join(SMOKE_FLOW_IDS)})"
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan only (no mutations)")
    parser.add_argument("--skip-validate", action="store_true", help="On apply, skip live HITL/webhook/MCP checks")
    parser.add_argument("--webhook-copy-max", type=int, default=None, help="Override minimum webhook copy count")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    _add_common_flags(common)

    parser = argparse.ArgumentParser(description="Langflow performance-suite provisioner")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("plan", "Print what would be created"),
        ("apply", "Create resources and write state"),
        ("validate", "Check state against live environment"),
        ("teardown", "Delete suite-tagged resources"),
    ):
        sub.add_parser(name, help=help_text, parents=[common])
    return parser


def _partition_flows(flow_ids: list[str], by_id: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    regular: list[str] = []
    webhook: list[str] = []
    for fid in flow_ids:
        entry = by_id[fid]
        if webhook_copy_count(entry) > 0:
            webhook.append(fid)
        else:
            regular.append(fid)
    return regular, webhook


def plan_resources(*, env_id: str, host: str, flow_ids: list[str], mode: str) -> dict[str, Any]:
    index = load_fixture_index()
    by_id = index_by_id(index)
    regular, webhook = _partition_flows(flow_ids, by_id)
    planned_flows = []
    for fid in regular:
        entry = by_id[fid]
        planned_flows.append(
            {
                "fixture_id": fid,
                "endpoint_name": tagged_endpoint_name(env_id, entry.get("endpoint_name"), fid),
                "mcp_action_name": entry.get("mcp_action_name"),
                "project": project_name(env_id, fid),
            }
        )
    planned_webhooks = []
    for fid in webhook:
        entry = by_id[fid]
        n = webhook_copy_count(entry)
        planned_webhooks.append({"fixture_id": fid, "copies": n})
    return {
        "env_id": env_id,
        "host": host,
        "mode": mode,
        "fixture_index_hash": fixture_index_hash(),
        "api_key": f"perf-{env_id}-key",
        "flows": planned_flows,
        "webhook_fixtures": planned_webhooks,
        "kb": needs_kb(flow_ids, by_id),
        "chat_seed": any(fid == "MemoryChatbotNoLLM" or fid.startswith("natural_memory_chatbot__") for fid in flow_ids),
        "hitl_validate": "human_input_flow" in flow_ids,
        "user_pool": mode == "superuser-pool",
    }


def cmd_plan(args: argparse.Namespace) -> int:
    env_id = args.env_id or _default_env_id()
    host = (args.host or _default_host()).rstrip("/")
    index = load_fixture_index()
    flow_ids = resolve_flow_ids(_split_flows(args.flows), index)
    plan = plan_resources(env_id=env_id, host=host, flow_ids=flow_ids, mode=args.mode)
    print(json.dumps(plan, indent=2))
    if args.dry_run:
        print("(dry-run: no changes)", file=sys.stderr)
    return 0


def _teardown_existing_if_present(
    http: ProvisionHttp,
    *,
    env_id: str,
    username: str | None,
    password: str | None,
) -> None:
    """Idempotent apply: remove a prior suite state for this env_id before recreating."""
    path = state_path_for(env_id)
    if not path.exists():
        return
    try:
        prior = load_state(env_id)
    except FileNotFoundError:
        return
    print(f"tearing down prior state for {env_id} before re-apply", file=sys.stderr)
    results = _teardown_provisioned_state(
        http,
        prior,
        username=username,
        password=password,
    )
    failures = _teardown_failures(results)
    if failures:
        print(json.dumps({"prior_teardown_failed": failures}, indent=2), file=sys.stderr)
        msg = f"prior teardown for {env_id!r} did not complete safely"
        raise RuntimeError(msg)
    try:
        path.unlink(missing_ok=True)
    except TypeError:
        if path.exists():
            path.unlink()


def _teardown_failures(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [result for result in results if result.get("status") not in {"deleted", "missing"}]


def _teardown_provisioned_state(
    http: ProvisionHttp,
    state: dict[str, Any],
    *,
    username: str | None,
    password: str | None,
) -> list[dict[str, Any]]:
    """Delete owner-scoped resources before deleting a suite user as administrator."""
    mode = str(state.get("mode") or "superuser_pool").replace("_", "-")
    credentials = state.get("credentials") or {}
    suite_username = credentials.get("suite_username")
    suite_password = credentials.get("password")

    if mode == "superuser-pool":
        if not suite_username or not suite_password:
            msg = "superuser-pool teardown state is missing suite-user credentials"
            raise RuntimeError(msg)
        http.login(str(suite_username), str(suite_password))
    else:
        authenticate(http, mode="existing-user", username=username, password=password)

    teardown_tokens = state.get("teardown_order") or []
    results = [{"token": str(token), "status": "invalid_token"} for token in teardown_tokens if ":" not in str(token)]
    resource_kinds = {str(token).split(":", 1)[0] for token in teardown_tokens if ":" in str(token)}
    owner_kinds = resource_kinds - {"user"}
    results.extend(teardown_state(http, state, resource_kinds=owner_kinds))

    if _teardown_failures(results):
        return results

    if "user" in resource_kinds:
        authenticate(http, mode="superuser-pool", username=username, password=password)
        results.extend(teardown_state(http, state, resource_kinds={"user"}))
    return results


def cmd_apply(args: argparse.Namespace) -> int:
    env_id = args.env_id or _default_env_id()
    host = (args.host or _default_host()).rstrip("/")
    index = load_fixture_index()
    flow_ids = resolve_flow_ids(_split_flows(args.flows), index)
    by_id = index_by_id(index)
    regular, webhook = _partition_flows(flow_ids, by_id)

    if args.dry_run:
        return cmd_plan(args)

    state = new_state(
        env_id=env_id,
        host=host,
        mode=args.mode.replace("-", "_"),
        fixture_index_hash=fixture_index_hash(),
    )
    # Pin per-flow fixture hashes for reproducibility / preflight.
    state["fixture_hashes"] = {
        fid: by_id[fid].get("fixture_sha256") for fid in flow_ids if fid in by_id and by_id[fid].get("fixture_sha256")
    }

    validation_errors: list[str] = []

    try:
        with ProvisionHttp(host) as http:
            http.health()
            authenticate(http, mode=args.mode, username=args.username, password=args.password)
            _teardown_existing_if_present(
                http,
                env_id=env_id,
                username=args.username,
                password=args.password,
            )
            # Re-auth after optional prior teardown (session may still be valid).
            authenticate(http, mode=args.mode, username=args.username, password=args.password)
            ensure_suite_user_pool(http, state, mode=args.mode)
            state["username"] = state.get("username") or (args.username or "unknown")

            create_suite_api_key(http, state)
            if needs_kb(flow_ids, by_id):
                provision_kb(http, state)
            if any(fid.startswith("natural_file_parser_agent__") for fid in flow_ids):
                uploaded = http.upload_user_file(
                    filename=f"perf-natural-{env_id}.txt",
                    content=bounded_payload_text().encode(),
                )
                state["natural_file"] = uploaded
                register_resource(
                    state,
                    kind="user_file",
                    resource_id=str(uploaded["id"]),
                    name=str(uploaded.get("name") or f"perf-natural-{env_id}.txt"),
                    env_id=env_id,
                )

            provision_flows(http, state, flow_ids=regular, index=index)
            provision_webhook_copies(
                http,
                state,
                flow_ids=webhook,
                index=index,
                profile_max=args.webhook_copy_max,
            )

            configure_mcp_for_state(http, state)

            if not args.skip_validate:
                if webhook and not validate_webhook_subscribe_before_post(http, state):
                    validation_errors.append("webhook subscribe-before-POST validation failed")
                if "human_input_flow" in flow_ids and not validate_hitl_lifecycle(http, state):
                    validation_errors.append("hitl lifecycle validation failed")
                if any((state.get("flows") or {}).get(fid, {}).get("mcp_action_name") for fid in regular):
                    if not validate_mcp_tools_listable(http, state):
                        validation_errors.append("mcp tools/list validation failed")
                if (
                    "MemoryChatbotNoLLM" in flow_ids
                    or any(fid.startswith("natural_memory_chatbot__") for fid in flow_ids)
                ) and not validation_errors:
                    seed_chat_history(http, state)
    except BaseException:
        # Resource helpers register each successful mutation immediately. Keep
        # that ownership record even when a later API call fails so teardown or
        # a retry can safely clean up the partial apply.
        if state.get("resources"):
            path = save_state(state)
            print(f"provision failed; wrote partial state: {path}", file=sys.stderr)
        raise

    path = save_state(state)
    print(json.dumps(redact_state_for_log(state), indent=2))
    print(f"wrote state: {path}", file=sys.stderr)

    if validation_errors:
        print(json.dumps({"ok": False, "errors": validation_errors}, indent=2), file=sys.stderr)
        return 1
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    env_id = args.env_id or _default_env_id()
    state = load_state(env_id)
    host = (args.host or state.get("host") or _default_host()).rstrip("/")
    errors: list[str] = []

    with ProvisionHttp(host, api_key=state.get("api_key"), bearer_token=None) as http:
        # Re-auth as the resource owner so owner-scoped flow fetches work. The
        # generated suite user owns everything in superuser-pool mode; logging
        # in as the administrator would correctly return 404 for those flows.
        try:
            state_mode = str(state.get("mode") or args.mode).replace("_", "-")
            if state_mode == "superuser-pool":
                credentials = state.get("credentials") or {}
                suite_username = credentials.get("suite_username")
                suite_password = credentials.get("password")
                if not suite_username or not suite_password:
                    msg = "superuser-pool validation state is missing suite-user credentials"
                    raise RuntimeError(msg)
                http.login(str(suite_username), str(suite_password))
            else:
                authenticate(http, mode="existing-user", username=args.username, password=args.password)
        except Exception as exc:
            errors.append(f"auth failed: {exc}")

        http.api_key = state.get("api_key")
        for fixture_id, record in (state.get("flows") or {}).items():
            flow = http.get_flow(str(record["flow_id"]))
            if flow is None:
                errors.append(f"flow missing: {fixture_id} ({record['flow_id']})")

        mcp_ok = (
            validate_mcp_tools_listable(http, state)
            if any(r.get("mcp_action_name") for r in (state.get("flows") or {}).values())
            else True
        )
        if not mcp_ok:
            errors.append("mcp tools/list validation failed")

        webhook_flag = (state.get("flags") or {}).get("webhook_validated") or (state.get("webhooks") or {}).get(
            "validated"
        )
        if (state.get("webhooks") or {}).get("copies") and not webhook_flag:
            if not validate_webhook_subscribe_before_post(http, state):
                errors.append("webhook subscribe-before-POST validation failed")

        hitl_flag = (state.get("flags") or {}).get("hitl_validated") or (state.get("hitl") or {}).get("usable")
        if "human_input_flow" in (state.get("flows") or {}) and not hitl_flag:
            if not validate_hitl_lifecycle(http, state):
                errors.append("hitl lifecycle validation failed")

        save_state(state)

    report = {
        "env_id": env_id,
        "ok": not errors,
        "errors": errors,
        "flags": state.get("flags"),
        "state_path": str(state_path_for(env_id)),
    }
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


def cmd_teardown(args: argparse.Namespace) -> int:
    env_id = args.env_id or _default_env_id()
    state = load_state(env_id)
    host = (args.host or state.get("host") or _default_host()).rstrip("/")

    if args.dry_run:
        print(json.dumps({"env_id": env_id, "teardown_order": state.get("teardown_order")}, indent=2))
        return 0

    with ProvisionHttp(host) as http:
        results = _teardown_provisioned_state(
            http,
            state,
            username=args.username,
            password=args.password,
        )
    print(json.dumps({"env_id": env_id, "results": results}, indent=2))
    failed = _teardown_failures(results)
    path = state_path_for(env_id)
    if not failed and path.exists():
        path.unlink()
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    commands = {
        "plan": cmd_plan,
        "apply": cmd_apply,
        "validate": cmd_validate,
        "teardown": cmd_teardown,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
