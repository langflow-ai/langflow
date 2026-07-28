"""Flow fixture import helpers driven by ``fixture_index.json``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.locust.langflow_runtime.flows.defaults import FLOWS_DIR
from tests.locust.langflow_runtime.hashing import sha256_file, sha256_text
from tests.locust.langflow_runtime.provision.api import ProvisionHttp
from tests.locust.langflow_runtime.provision.projects import create_isolated_project
from tests.locust.langflow_runtime.provision.state import register_resource

FIXTURE_INDEX_PATH = FLOWS_DIR / "fixture_index.json"


def load_fixture_index(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or FIXTURE_INDEX_PATH).read_text(encoding="utf-8"))


def fixture_index_hash(path: Path | None = None) -> str:
    return sha256_file(path or FIXTURE_INDEX_PATH)


def index_by_id(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(entry["id"]): entry for entry in index.get("flows", [])}


def resolve_flow_ids(requested: list[str] | None, index: dict[str, Any]) -> list[str]:
    """Resolve ``--flows`` selection by fixture id or named scope."""
    from tests.locust.langflow_runtime.provision import SMOKE_FLOW_IDS

    available = index_by_id(index)
    if not requested or (len(requested) == 1 and requested[0].lower() in {"default", "full", "all"}):
        return [str(entry["id"]) for entry in index.get("flows", [])]

    if len(requested) == 1 and requested[0].lower() == "smoke":
        missing = [fid for fid in SMOKE_FLOW_IDS if fid not in available]
        if missing:
            msg = f"smoke flow ids missing from fixture_index: {missing}"
            raise RuntimeError(msg)
        return list(SMOKE_FLOW_IDS)

    unknown = [fid for fid in requested if fid not in available]
    if unknown:
        msg = f"unknown fixture ids (not in fixture_index): {unknown}"
        raise RuntimeError(msg)
    return list(requested)


def load_fixture_payload(entry: dict[str, Any]) -> dict[str, Any]:
    path = FLOWS_DIR / entry["fixture_path"]
    return json.loads(path.read_text(encoding="utf-8"))


def tagged_endpoint_name(env_id: str, base_endpoint: str | None, fixture_id: str) -> str:
    """Build ``perf-{env_id}-…`` endpoint names safe for URL use."""
    base = (base_endpoint or fixture_id).strip()
    if base.startswith("perf-"):
        suffix = base[len("perf-") :]
    else:
        suffix = base
    # Endpoint names allow only [a-zA-Z0-9_-]
    safe_env = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in env_id)
    return f"perf-{safe_env}-{suffix}"


def flow_display_name(env_id: str, fixture_id: str) -> str:
    return f"perf-{env_id}-{fixture_id}"


def _set_node_field(payload: dict[str, Any], node_type: str, field_name: str, value: str) -> None:
    for node in payload.get("data", {}).get("nodes", []):
        data = node.get("data") or {}
        if data.get("type") != node_type:
            continue
        field = ((data.get("node") or {}).get("template") or {}).get(field_name)
        if isinstance(field, dict):
            field["value"] = value


def _bind_uploaded_file(payload: dict[str, Any], file_record: dict[str, Any]) -> None:
    path = str(file_record["path"])
    for node in payload.get("data", {}).get("nodes", []):
        data = node.get("data") or {}
        if data.get("type") != "File":
            continue
        template = (data.get("node") or {}).get("template") or {}
        path_field = template.get("path")
        if isinstance(path_field, dict):
            path_field["value"] = [path]
            path_field["file_path"] = [path]


def import_flow(
    http: ProvisionHttp,
    state: dict[str, Any],
    entry: dict[str, Any],
    *,
    copy_index: int | None = None,
) -> dict[str, Any]:
    """Create an isolated project and import one fixture flow into it."""
    env_id = str(state["env_id"])
    fixture_id = str(entry["id"])
    label = fixture_id if copy_index is None else f"{fixture_id}-copy-{copy_index}"
    project = create_isolated_project(http, state, fixture_id=label)
    project_id = str(project["id"])

    payload = load_fixture_payload(entry)
    kb_name = (state.get("kb") or {}).get("name")
    if kb_name:
        _set_node_field(payload, "Knowledge", "knowledge_base", str(kb_name))
    natural_file = state.get("natural_file")
    if fixture_id.startswith("natural_file_parser_agent__") and isinstance(natural_file, dict):
        _bind_uploaded_file(payload, natural_file)
    memory_base_name = None
    if fixture_id.startswith("natural_memory_chatbot__"):
        memory_base_name = f"perf-memory-{env_id}-{fixture_id}"[:120]
        _set_node_field(payload, "MemoryBase", "memory_base", memory_base_name)
    endpoint = tagged_endpoint_name(env_id, entry.get("endpoint_name"), fixture_id)
    if copy_index is not None:
        endpoint = f"{endpoint}-{copy_index}"

    mcp_action = entry.get("mcp_action_name")
    wants_mcp = bool(mcp_action) or "mcp" in (entry.get("supported_protocols") or [])
    is_webhook = "webhook" in (entry.get("supported_protocols") or []) or entry.get("webhook_copy_count", 0) > 0

    body: dict[str, Any] = {
        "name": flow_display_name(env_id, label),
        "description": f"perf suite fixture {fixture_id} ({env_id})",
        "data": payload.get("data", payload),
        "endpoint_name": endpoint,
        "folder_id": project_id,
        "mcp_enabled": wants_mcp and copy_index is None,
        "action_name": mcp_action if wants_mcp and copy_index is None else None,
        "webhook": is_webhook,
    }
    # Prefer create_flow for explicit field control.
    created = http.create_flow(body)
    flow_id = str(created["id"])
    fixture_hash = entry.get("fixture_sha256") or sha256_text(json.dumps(payload, sort_keys=True))

    record = {
        "flow_id": flow_id,
        "endpoint_name": endpoint,
        "mcp_action_name": mcp_action,
        "fixture_id": fixture_id,
        "fixture_sha256": fixture_hash,
        "project_id": project_id,
        "env_id": env_id,
        "copy_index": copy_index,
    }
    register_resource(
        state,
        kind="flow",
        resource_id=flow_id,
        name=body["name"],
        env_id=env_id,
        extra={"fixture_id": fixture_id, "project_id": project_id},
    )
    if memory_base_name is not None:
        memory_base = http.create_memory_base(name=memory_base_name, flow_id=flow_id)
        memory_base_id = str(memory_base["id"])
        state.setdefault("memory_bases", {})[fixture_id] = {
            "id": memory_base_id,
            "name": memory_base_name,
            "flow_id": flow_id,
            "kb_name": memory_base.get("kb_name"),
        }
        register_resource(
            state,
            kind="memory_base",
            resource_id=memory_base_id,
            name=memory_base_name,
            env_id=env_id,
            extra={"fixture_id": fixture_id, "flow_id": flow_id},
        )
    return record


def provision_flows(
    http: ProvisionHttp,
    state: dict[str, Any],
    *,
    flow_ids: list[str],
    index: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    idx = index or load_fixture_index()
    by_id = index_by_id(idx)
    flows: dict[str, dict[str, Any]] = state.setdefault("flows", {})
    for fixture_id in flow_ids:
        entry = by_id[fixture_id]
        record = import_flow(http, state, entry)
        flows[fixture_id] = record
        if not state.get("project_id") and record.get("project_id"):
            state["project_id"] = record["project_id"]
    return flows
