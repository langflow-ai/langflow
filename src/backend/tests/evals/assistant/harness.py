"""Structural helpers for assistant eval checks.

Pure functions over parsed SSE event dicts — no LLM, no network — so the
normal unit suite can prove each check catches the failure it claims to.
"""

from __future__ import annotations

import copy
import json
from typing import Any

Event = dict[str, Any]
FlowData = dict[str, Any]

_DATA_PREFIX = "data: "


def parse_sse_payloads(raw: str) -> list[Event]:
    """Parse an SSE body into the list of JSON payloads carried by ``data:`` lines."""
    events: list[Event] = []
    for line in raw.splitlines():
        if not line.startswith(_DATA_PREFIX):
            continue
        try:
            payload = json.loads(line[len(_DATA_PREFIX) :])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def events_of(events: list[Event], kind: str) -> list[Event]:
    return [e for e in events if e.get("event") == kind]


def flow_updates(events: list[Event]) -> list[Event]:
    return events_of(events, "flow_update")


def error_events(events: list[Event]) -> list[Event]:
    return events_of(events, "error")


def complete_data(events: list[Event]) -> dict[str, Any] | None:
    """Return the payload of the LAST complete event, or None when the turn never completed."""
    completes = events_of(events, "complete")
    if not completes:
        return None
    data = completes[-1].get("data")
    return data if isinstance(data, dict) else {}


def total_tokens(events: list[Event]) -> int | None:
    data = complete_data(events)
    if data is None:
        return None
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return None
    value = usage.get("total_tokens")
    return int(value) if isinstance(value, (int, float)) else None


def duration_seconds(events: list[Event]) -> float | None:
    data = complete_data(events)
    if data is None:
        return None
    value = data.get("duration_seconds")
    return float(value) if isinstance(value, (int, float)) else None


def max_attempt(events: list[Event]) -> int:
    """Highest ``attempt`` seen on progress events (0 when none were emitted)."""
    attempts = [int(e["attempt"]) for e in events_of(events, "progress") if isinstance(e.get("attempt"), (int, float))]
    return max(attempts, default=0)


def result_text(events: list[Event]) -> str:
    data = complete_data(events)
    if data is None:
        return ""
    value = data.get("result")
    return value if isinstance(value, str) else ""


def _node_id(node: dict[str, Any]) -> str:
    return str(node.get("data", {}).get("id", node.get("id", "")))


def _apply_configure(data: FlowData, event: Event) -> None:
    params = event.get("params")
    component_id = event.get("component_id")
    if not isinstance(params, dict) or not component_id:
        return
    for node in data.get("nodes", []):
        if _node_id(node) != component_id:
            continue
        template = node.get("data", {}).get("node", {}).get("template", {})
        for key, value in params.items():
            if isinstance(template.get(key), dict):
                template[key]["value"] = value
        return


def _apply_edit_field(data: FlowData, event: Event) -> None:
    component_id = event.get("component_id")
    fld = event.get("field")
    if not component_id or not fld:
        return
    for node in data.get("nodes", []):
        if _node_id(node) != component_id:
            continue
        template = node.get("data", {}).get("node", {}).get("template", {})
        if isinstance(template.get(fld), dict):
            template[fld]["value"] = event.get("new_value")
        return


def replay_final_flow(initial_data: FlowData | None, events: list[Event]) -> FlowData:
    """Replay flow_update events over the seed canvas to reconstruct the proposed final flow.

    Mirrors the server-side fallback replay (set_flow / add_component / connect /
    remove_component) plus configure and edit_field so field-level checks work.
    """
    data: FlowData = copy.deepcopy(initial_data) if initial_data else {}
    data.setdefault("nodes", [])
    data.setdefault("edges", [])
    for event in flow_updates(events):
        action = event.get("action")
        if action == "set_flow":
            flow = event.get("flow")
            if isinstance(flow, dict) and isinstance(flow.get("data"), dict):
                data = copy.deepcopy(flow["data"])
                data.setdefault("nodes", [])
                data.setdefault("edges", [])
        elif action == "add_component" and isinstance(event.get("node"), dict):
            node = event["node"]
            data["nodes"] = [n for n in data["nodes"] if n.get("id") != node.get("id")]
            data["nodes"].append(copy.deepcopy(node))
        elif action == "remove_component" and event.get("component_id"):
            component_id = event["component_id"]
            data["nodes"] = [n for n in data["nodes"] if _node_id(n) != component_id]
            data["edges"] = [e for e in data["edges"] if component_id not in (e.get("source"), e.get("target"))]
        elif action == "connect" and isinstance(event.get("edge"), dict):
            edge = event["edge"]
            data["edges"] = [e for e in data["edges"] if e.get("id") != edge.get("id")]
            data["edges"].append(copy.deepcopy(edge))
        elif action == "configure":
            _apply_configure(data, event)
        elif action == "edit_field":
            _apply_edit_field(data, event)
    return data


def node_type(node: dict[str, Any]) -> str:
    return str(node.get("data", {}).get("type", ""))


def node_types(data: FlowData) -> list[str]:
    return [node_type(n) for n in data.get("nodes", [])]


def nodes_of_type(data: FlowData, type_name: str) -> list[dict[str, Any]]:
    return [n for n in data.get("nodes", []) if node_type(n) == type_name]


def template_value(node: dict[str, Any], fld: str) -> Any:
    entry = node.get("data", {}).get("node", {}).get("template", {}).get(fld)
    return entry.get("value") if isinstance(entry, dict) else None


def is_loop_feedback_edge(edge: dict[str, Any]) -> bool:
    """A loop feedback edge targets an OUTPUT-shaped handle: ``name`` key, no ``fieldName``."""
    handle = edge.get("data", {}).get("targetHandle")
    return isinstance(handle, dict) and "name" in handle and "fieldName" not in handle


def loop_feedback_edges(data: FlowData) -> list[dict[str, Any]]:
    return [e for e in data.get("edges", []) if is_loop_feedback_edge(e)]


def edges_from_output(data: FlowData, output_name: str) -> list[dict[str, Any]]:
    """Edges whose source handle is the named output (e.g. ConditionalRouter true_result)."""
    matched: list[dict[str, Any]] = []
    for edge in data.get("edges", []):
        handle = edge.get("data", {}).get("sourceHandle")
        if isinstance(handle, dict) and handle.get("name") == output_name:
            matched.append(edge)
    return matched


def structural_completeness_failures(data: FlowData) -> list[str]:
    """Run the SAME structural validator the assistant gates delivery on.

    Asserts the applied canvas (not just the proposal shape) is runnable-
    structure: required inputs connected/set, loop data source present, loop
    body closed, no orphans. Single source of truth with the delivery gate.
    """
    from langflow.agentic.services.flow_structural_validation import structural_failures

    return structural_failures({"data": data})


def baseline_failures(
    events: list[Event],
    *,
    expect_flow_update: bool | None,
    token_ceiling: int,
    duration_ceiling: float,
) -> list[str]:
    """Shared structural gate: completion, no errors, single attempt, flow_update presence, budgets."""
    failures: list[str] = []
    errors = error_events(events)
    if errors:
        failures.append(f"error event(s) emitted: {[e.get('message') for e in errors]}")
    if complete_data(events) is None:
        failures.append("no complete event (turn never finished)")
    attempt = max_attempt(events)
    if attempt > 1:
        failures.append(f"needed {attempt} attempts (retry loop engaged)")
    updates = flow_updates(events)
    if expect_flow_update is True and not updates:
        failures.append("expected flow_update events but none were emitted")
    if expect_flow_update is False and updates:
        failures.append(f"expected NO flow_update events but saw {len(updates)}")
    tokens = total_tokens(events)
    if tokens is not None and tokens > token_ceiling:
        failures.append(f"token budget exceeded: {tokens} > {token_ceiling}")
    duration = duration_seconds(events)
    if duration is not None and duration > duration_ceiling:
        failures.append(f"duration budget exceeded: {duration:.1f}s > {duration_ceiling:.0f}s")
    return failures
