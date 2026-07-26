"""Validate the V1 performance-suite flow fixtures against flows/fixture_index.json.

Step 1 gate: fixture_index contracts, binding checks, optional ``Graph.from_payload``
import, and optional in-process one-run for isolators that do not need external
services. Live HTTP protocol coverage (webhook SSE, HITL pending/resume,
background queue admission, KB directory provisioning, outbound keys) lives in
``tests/locust/tests/integration/``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

from tests.locust.langflow_runtime.datasets.registry import DATASET_IDS
from tests.locust.langflow_runtime.flows.defaults import (
    DEFAULT_KB_NAME,
    DEFAULT_OUTBOUND_MODEL,
    DEFAULT_OUTBOUND_PROVIDER,
)
from tests.locust.langflow_runtime.hashing import component_source_hashes, embedded_isolator_hashes, sha256_file

FLOWS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = FLOWS_DIR / "fixtures"
COMPONENTS_DIR = FLOWS_DIR.parent / "components"
FIXTURE_INDEX_PATH = FLOWS_DIR / "fixture_index.json"

REQUIRED_STRESS_CATEGORIES = {
    "protocol_calibration",
    "webhook",
    "chat_db",
    "hitl",
    "queue",
    "kb_ingest",
    "kb_retrieve",
    "cpu_graph",
    "multiproc",
    "disk_io",
    "ram_storage",
    "outbound",
    "ensemble_flow",
    "ensemble_flow_hitl",
}

HITL_FORBIDDEN_PROTOCOLS = {"mcp", "webhook"}

REQUIRED_FLOW_KEYS = {
    "id",
    "fixture",
    "fixture_path",
    "fixture_sha256",
    "stress_category",
    "source_provenance",
    "supported_protocols",
    "supported_modes",
    "input_fields",
    "expected_output_rule",
    "required_environment_features",
    "dataset_selector",
    "webhook_copy_count",
    "hitl",
    "endpoint_name",
    "stores_chat_history",
}


class ValidationError(Exception):
    """One or more fixture contract checks failed."""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _graph_shape_ok(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    data = payload.get("data")
    if not isinstance(data, dict):
        return ["missing data object"]
    nodes = data.get("nodes")
    edges = data.get("edges")
    if not isinstance(nodes, list) or not nodes:
        errors.append("data.nodes must be a non-empty list")
    if not isinstance(edges, list):
        errors.append("data.edges must be a list")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                errors.append("node is not an object")
                continue
            node_data = node.get("data") or {}
            if "type" not in node_data:
                errors.append(f"node {node.get('id')} missing data.type")
            if "node" not in node_data:
                errors.append(f"node {node.get('id')} missing data.node")
    return errors


def _has_secret_literals(payload: dict[str, Any]) -> list[str]:
    """Reject obvious embedded credentials (not a full secret scanner)."""
    text = json.dumps(payload)
    patterns = [
        r"sk-[A-Za-z0-9]{20,}",
        r"OPENAI_API_KEY\s*=\s*['\"][^'\"]+['\"]",
        r"-----BEGIN (RSA |EC )?PRIVATE KEY-----",
    ]
    return [pattern for pattern in patterns if re.search(pattern, text)]


def _fixture_path_contained(fixture_path: Path) -> bool:
    try:
        fixture_path.resolve().relative_to(FIXTURES_DIR.resolve())
    except ValueError:
        return False
    return True


def chat_store_message_settings(payload: dict[str, Any]) -> list[tuple[str, Any]]:
    """Return ``(node_type, should_store_message)`` for Chat Input/Output nodes."""
    settings: list[tuple[str, Any]] = []
    for node in payload.get("data", {}).get("nodes", []):
        node_data = node.get("data") or {}
        node_type = node_data.get("type")
        if node_type not in {"ChatInput", "ChatOutput"}:
            continue
        template = (node_data.get("node") or {}).get("template") or {}
        field = template.get("should_store_message")
        if not isinstance(field, dict):
            settings.append((node_type, None))
            continue
        settings.append((node_type, field.get("value")))
    return settings


def _validate_chat_history_policy(flow_id: str, flow: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    """Ensure Chat* Store Messages matches the flow's ``stores_chat_history`` contract."""
    if "stores_chat_history" not in flow:
        return []
    expected = flow["stores_chat_history"]
    if not isinstance(expected, bool):
        return [f"{flow_id}: stores_chat_history must be a bool"]

    settings = chat_store_message_settings(payload)
    errors: list[str] = []
    if expected:
        if not settings:
            errors.append(f"{flow_id}: stores_chat_history=true but fixture has no ChatInput/ChatOutput")
        for node_type, value in settings:
            if value is not True:
                errors.append(
                    f"{flow_id}: {node_type} should_store_message must be true "
                    f"(got {value!r}; flow stores_chat_history=true)"
                )
        return errors

    for node_type, value in settings:
        if value is not False:
            errors.append(
                f"{flow_id}: {node_type} should_store_message must be false "
                f"(got {value!r}; flow stores_chat_history=false — isolators must not write chat history)"
            )
    return errors


def validate_fixture_index(manifest: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    if manifest is None:
        if not FIXTURE_INDEX_PATH.exists():
            return [f"missing fixture_index: {FIXTURE_INDEX_PATH}"]
        manifest = _load_json(FIXTURE_INDEX_PATH)

    if manifest.get("version") != 1:
        errors.append(f"fixture_index.version must be 1 (got {manifest.get('version')!r})")

    flows = manifest.get("flows")
    if not isinstance(flows, list) or not flows:
        return [*errors, "fixture_index.flows must be a non-empty list"]

    hashes = component_source_hashes(COMPONENTS_DIR)
    declared = manifest.get("component_source_sha256") or {}
    for key, digest in hashes.items():
        if declared.get(key) != digest:
            errors.append(f"component_source_sha256[{key}] mismatch (rebuild fixtures)")

    endpoint_names: dict[str, str] = {}
    action_names: dict[str, str] = {}
    categories: set[str] = set()
    fixture_files_on_disk = {p.name for p in FIXTURES_DIR.glob("*.json")} if FIXTURES_DIR.exists() else set()
    listed_fixtures: set[str] = set()

    for flow in flows:
        flow_id = flow.get("id", "<unknown>")
        missing_keys = sorted(REQUIRED_FLOW_KEYS - set(flow))
        if missing_keys:
            errors.append(f"{flow_id}: missing required contract keys {missing_keys}")

        if flow.get("source_provenance") and "/home/" in str(flow["source_provenance"]):
            errors.append(f"{flow_id}: source_provenance must be repo-relative (no absolute host paths)")

        fixture_rel = flow.get("fixture_path") or f"fixtures/{flow.get('fixture')}"
        fixture_path = (FLOWS_DIR / fixture_rel).resolve()
        listed_fixtures.add(Path(fixture_rel).name)

        if not _fixture_path_contained(fixture_path):
            errors.append(f"{flow_id}: fixture_path escapes fixtures dir ({fixture_rel})")
            continue

        if not fixture_path.exists():
            errors.append(f"{flow_id}: missing fixture {fixture_path}")
            continue

        actual_hash = sha256_file(fixture_path)
        if flow.get("fixture_sha256") != actual_hash:
            errors.append(f"{flow_id}: fixture_sha256 mismatch (got {actual_hash})")

        payload = _load_json(fixture_path)
        errors.extend(f"{flow_id}: {shape_error}" for shape_error in _graph_shape_ok(payload))
        errors.extend(
            f"{flow_id}: possible embedded secret matching {secret_pat}" for secret_pat in _has_secret_literals(payload)
        )
        errors.extend(_validate_chat_history_policy(flow_id, flow, payload))

        endpoint = payload.get("endpoint_name") or flow.get("endpoint_name")
        if not endpoint:
            errors.append(f"{flow_id}: missing endpoint_name")
        elif endpoint in endpoint_names:
            errors.append(f"{flow_id}: duplicate endpoint_name {endpoint!r} (also {endpoint_names[endpoint]})")
        else:
            endpoint_names[endpoint] = flow_id

        action = flow.get("mcp_action_name")
        if action:
            if action in action_names:
                errors.append(f"{flow_id}: duplicate mcp_action_name {action!r} (also {action_names[action]})")
            else:
                action_names[action] = flow_id

        category = flow.get("stress_category")
        if category:
            categories.add(category)

        protocols = set(flow.get("supported_protocols") or [])
        if flow.get("hitl") and protocols & HITL_FORBIDDEN_PROTOCOLS:
            errors.append(
                f"{flow_id}: HITL flows must not declare MCP/Webhooks "
                f"(got {sorted(protocols & HITL_FORBIDDEN_PROTOCOLS)})"
            )
        if not protocols:
            errors.append(f"{flow_id}: supported_protocols must be non-empty")
        if not flow.get("supported_modes"):
            errors.append(f"{flow_id}: supported_modes must be non-empty")

        if "input_fields" in flow and not isinstance(flow["input_fields"], dict):
            errors.append(f"{flow_id}: input_fields must be an object")
        if "expected_output_rule" in flow and not isinstance(flow["expected_output_rule"], dict):
            errors.append(f"{flow_id}: expected_output_rule must be an object")
        if "webhook_copy_count" in flow and not isinstance(flow["webhook_copy_count"], int):
            errors.append(f"{flow_id}: webhook_copy_count must be an int")

        expected_components = flow.get("embedded_components") or []
        embedded = embedded_isolator_hashes(payload)
        for key in expected_components:
            if key not in embedded:
                errors.append(f"{flow_id}: expected embedded component {key} not found in fixture")
            elif embedded[key] != hashes[key]:
                errors.append(
                    f"{flow_id}: embedded {key} source hash mismatch "
                    f"(fixture={embedded[key][:12]}… file={hashes[key][:12]}…)"
                )
            declared_expected = (flow.get("expected_component_sha256") or {}).get(key)
            if declared_expected and declared_expected != hashes[key]:
                errors.append(f"{flow_id}: expected_component_sha256[{key}] stale")

        dataset_selector = flow.get("dataset_selector")
        if dataset_selector and dataset_selector not in DATASET_IDS:
            errors.append(f"{flow_id}: dataset_selector {dataset_selector} not in DATASET_IDS")

    missing_categories = REQUIRED_STRESS_CATEGORIES - categories
    if missing_categories:
        errors.append(f"missing stress categories: {sorted(missing_categories)}")

    orphan_fixtures = fixture_files_on_disk - listed_fixtures
    if orphan_fixtures:
        errors.append(f"orphan fixtures not in fixture_index: {sorted(orphan_fixtures)}")

    errors.extend(validate_fixture_bindings(manifest))
    return errors


def validate_fixture_bindings(manifest: dict[str, Any] | None = None) -> list[str]:
    """Static checks that KB/outbound fixtures declare the subsystems they need."""
    errors: list[str] = []
    if manifest is None:
        if not FIXTURE_INDEX_PATH.exists():
            return ["missing fixture_index"]
        manifest = _load_json(FIXTURE_INDEX_PATH)
    for flow in manifest["flows"]:
        fixture_path = FLOWS_DIR / flow["fixture_path"]
        if not fixture_path.exists():
            continue
        payload = _load_json(fixture_path)
        nodes = payload.get("data", {}).get("nodes", [])
        types = {n.get("data", {}).get("type") for n in nodes}
        if "KnowledgeIngestion" in types or "KnowledgeBase" in types:
            kb_values = [
                ((node.get("data") or {}).get("node") or {}).get("template", {}).get("knowledge_base", {}).get("value")
                for node in nodes
                if node.get("data", {}).get("type") in {"KnowledgeIngestion", "KnowledgeBase"}
            ]
            if not any(kb_values):
                errors.append(f"{flow['id']}: knowledge_base binding is empty (subsystem cannot run)")
            expected = (flow.get("binding") or {}).get("knowledge_base", DEFAULT_KB_NAME)
            if expected and expected not in kb_values:
                errors.append(f"{flow['id']}: knowledge_base values {kb_values!r} missing expected {expected!r}")
        if flow["id"] in {"perf_outbound_basic_prompting", "perf_ensemble_journey", "perf_ensemble_journey_hitl"}:
            for node in nodes:
                if node.get("data", {}).get("type") != "LanguageModelComponent":
                    continue
                template = ((node.get("data") or {}).get("node") or {}).get("template") or {}
                provider = (template.get("provider") or {}).get("value")
                model_name = (template.get("model_name") or {}).get("value")
                model = (template.get("model") or {}).get("value")
                api_key = template.get("api_key") or {}
                if not provider and not model:
                    errors.append(f"{flow['id']}: outbound provider unset and model selection empty")
                if provider and provider != DEFAULT_OUTBOUND_PROVIDER:
                    errors.append(f"{flow['id']}: outbound provider {provider!r} != {DEFAULT_OUTBOUND_PROVIDER!r}")
                if model_name and model_name != DEFAULT_OUTBOUND_MODEL:
                    errors.append(f"{flow['id']}: outbound model_name {model_name!r} != {DEFAULT_OUTBOUND_MODEL!r}")
                if not api_key.get("load_from_db"):
                    errors.append(f"{flow['id']}: outbound api_key must use load_from_db (no embedded secrets)")
                if isinstance(api_key.get("value"), str) and api_key["value"].startswith("sk-"):
                    errors.append(f"{flow['id']}: outbound api_key looks like an embedded secret")
    return errors


def validate_importable(flow_ids: list[str] | None = None) -> list[str]:
    """Offline Graph.from_payload round-trip (Step 1). Not a live Langflow API import."""
    from lfx.graph import Graph

    errors: list[str] = []
    manifest = _load_json(FIXTURE_INDEX_PATH)
    for flow in manifest["flows"]:
        if flow_ids and flow["id"] not in flow_ids:
            continue
        fixture_path = FLOWS_DIR / flow["fixture_path"]
        payload = _load_json(fixture_path)
        try:
            graph = Graph.from_payload(payload["data"])
            if not graph.vertices:
                errors.append(f"{flow['id']}: from_payload produced no vertices")
        except Exception as exc:
            errors.append(f"{flow['id']}: Graph.from_payload failed: {exc}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--import-check",
        action="store_true",
        help="Also round-trip every fixture through Graph.from_payload (offline Step 1 gate).",
    )
    parser.add_argument(
        "--one-run",
        action="store_true",
        help=(
            "Execute in-process one-runs for isolators that do not need external "
            "KB/LLM/webhook bindings (message-store and output-contract checks)."
        ),
    )
    parser.add_argument(
        "--flow",
        action="append",
        dest="flows",
        help="Limit --import-check / --one-run to one or more flow ids.",
    )
    args = parser.parse_args(argv)

    errors = validate_fixture_index()
    if args.import_check:
        errors.extend(validate_importable(args.flows))
    if args.one_run:
        from tests.locust.langflow_runtime.flows.one_run import validate_one_runs

        errors.extend(asyncio.run(validate_one_runs(args.flows)))

    if errors:
        print(f"FAILED ({len(errors)} issue(s)):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    manifest = _load_json(FIXTURE_INDEX_PATH)
    print(f"OK: {len(manifest['flows'])} flows validated against {FIXTURE_INDEX_PATH.name}")
    if args.import_check:
        print("OK: Graph.from_payload import check passed")
    if args.one_run:
        print("OK: in-process one-run checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
