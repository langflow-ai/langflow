"""Validate and compose an Instructions flow without executing stored component code."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from pydantic import BaseModel, ConfigDict, Field

BINDING_ORIGIN = "_harness_binding"


class FlowBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    flow_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    output_name: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    version_id: str | None = None


def flow_revision(data: dict) -> str:
    """Identify the saved definition, ignoring canvas selection and positioning."""
    definition = {
        "nodes": [{"id": node["id"], "data": node.get("data", {})} for node in data.get("nodes", [])],
        "edges": data.get("edges", []),
    }
    return hashlib.sha256(json.dumps(definition, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def instruction_outputs(data: dict) -> list[dict]:
    """Eligible declared terminals. Graph parsing is deliberately component-free."""
    return contract_outputs(data, {"Message", "str", "Text"}, require_output_component=False)


def validate_instruction_result(value):
    """Validate the actual text carrier while preserving its type on the flow edge."""
    from lfx.schema.message import Message

    text = value.text if isinstance(value, Message) else value
    if not isinstance(text, str) or not text.strip():
        msg = "The bound Instructions flow did not return non-empty text."
        raise ValueError(msg)
    return value


def contract_outputs(data: dict, output_types: set[str], *, require_output_component: bool = True) -> list[dict]:
    """Inspect declared terminal types and configured inputs without loading component code."""
    from lfx.graph.graph.base import Graph

    graph = Graph.from_payload(deepcopy(data), instantiate_components=False, emit_extension_events=False)
    connected = {
        (edge.get("target"), edge.get("data", {}).get("targetHandle", {}).get("fieldName"))
        for edge in data.get("edges", [])
    }
    for node in data.get("nodes", []):
        for name, entry in node.get("data", {}).get("node", {}).get("template", {}).items():
            if not isinstance(entry, dict) or name in {"code", "_type"}:
                continue
            value = entry.get("value")
            missing = value in (None, "", []) or (isinstance(value, str) and not value.strip())
            if entry.get("required") and missing and (node["id"], name) not in connected:
                display_name = node.get("data", {}).get("node", {}).get("display_name", node["id"])
                msg = f"Configure {display_name}: {entry.get('display_name', name)}."
                raise ValueError(msg)
    choices = []
    for vertex in graph.vertices:
        if (require_output_component and not vertex.is_output) or graph.successor_map.get(vertex.id):
            continue
        choices.extend(
            {
                "node_id": vertex.id,
                "output_name": output["name"],
                "display_name": f"{vertex.display_name} · {output.get('display_name', output['name'])}",
            }
            for output in vertex.outputs
            if output.get("types") and set(output["types"]) <= output_types
        )
    return choices


def validate_instruction_binding(data: dict, binding: FlowBinding) -> None:
    choices = instruction_outputs(data)
    if not any(
        choice["node_id"] == binding.node_id and choice["output_name"] == binding.output_name for choice in choices
    ):
        msg = "The selected Instructions output is missing or no longer produces text. Choose a compatible output."
        raise ValueError(msg)
    if flow_revision(data) != binding.revision:
        msg = "The Instructions flow has changed. Review it and update the binding on the harness before running."
        raise ValueError(msg)


def reject_recursive_binding(flows: list[dict], target_id: str, agent_id: str) -> None:
    """Reject any local invocation cycle reachable from the selected flow."""
    by_id = {flow["id"]: flow for flow in flows}
    by_name: dict[str, list[str]] = {}
    for flow in flows:
        by_name.setdefault(flow["name"], []).append(flow["id"])
    visited: set[str] = set()

    def visit(flow_id: str, active: set[str]) -> None:
        if flow_id == agent_id or flow_id in active:
            msg = "The Instructions flow contains a recursive flow reference."
            raise ValueError(msg)
        if flow_id in visited or flow_id not in by_id:
            return
        active = active | {flow_id}
        for node in (by_id[flow_id].get("data") or {}).get("nodes", []):
            data = node.get("data", {})
            if data.get("type") not in {"RunFlow", "SubFlow"}:
                continue
            template = data.get("node", {}).get("template", {})
            selected_id = template.get("flow_id_selected", {}).get("value")
            selected_name = template.get("flow_name_selected", template.get("flow_name", {})).get("value")
            for target in [selected_id] if selected_id else by_name.get(selected_name, []):
                visit(target, active)
        visited.add(flow_id)

    visit(target_id, set())


def compose_instructions(
    data: dict, *, project_id: str, agent_id: str, target: dict | None, binding: FlowBinding | None
) -> dict:
    """Reconcile one generated connection. Never replace a user's existing prompt edge."""
    from lfx.components.flow_controls.run_flow import RunFlowComponent
    from lfx.graph.flow_builder import add_component, add_connection, remove_component
    from lfx.graph.graph.base import Graph
    from lfx.schema.dotdict import dotdict

    flow = {"data": deepcopy(data)}
    existing = []
    for node in list(flow["data"]["nodes"]):
        origin = node.get("data", {}).get(BINDING_ORIGIN)
        if (
            isinstance(origin, dict)
            and origin.get("project_id") == project_id
            and origin.get("field_name") == "system_prompt"
        ):
            existing.append(node)
    incoming = [
        edge
        for edge in data.get("edges", [])
        if edge.get("target") == agent_id
        and edge.get("data", {}).get("targetHandle", {}).get("fieldName") == "system_prompt"
    ]
    generated_ids = {node["id"] for node in existing}
    if any(
        (edge.get("source") in generated_ids and edge not in incoming) or edge.get("target") in generated_ids
        for edge in data.get("edges", [])
    ):
        msg = "The Instructions node has custom canvas connections. Disconnect them before changing the binding."
        raise ValueError(msg)
    if binding is not None and any(edge.get("source") not in generated_ids for edge in incoming):
        msg = "Instructions already has a canvas connection. Remove that connection before binding a flow."
        raise ValueError(msg)
    origin = {"project_id": project_id, "field_name": "system_prompt", **binding.model_dump()} if binding else None
    if len(existing) == 1 and existing[0]["data"].get(BINDING_ORIGIN) == origin:
        template = existing[0]["data"]["node"]["template"]
        if (
            len(incoming) != 1
            or incoming[0].get("source") != existing[0]["id"]
            or incoming[0].get("data", {}).get("sourceHandle", {}).get("name")
            != f"{binding.node_id}~{binding.output_name}"
            or template.get("flow_id_selected", {}).get("value") != binding.flow_id
        ):
            msg = "The Instructions connection was edited on the canvas. Remove the binding before replacing it."
            raise ValueError(msg)
        return flow["data"]
    for node in existing:
        remove_component(flow, node["id"])
    if binding is None or target is None:
        return flow["data"]

    graph = Graph.from_payload(deepcopy(target["data"]), instantiate_components=False, emit_extension_events=False)
    component = RunFlowComponent()
    node = component.to_frontend_node()["data"]["node"]
    template = dotdict(node["template"])
    # Instructions flows run with their own configured inputs, not stale exposed input copies.
    template["flow_name_selected"].update(value=target["name"], options=[target["name"]])
    template["flow_id_selected"]["value"] = binding.flow_id
    template["cache_flow"]["value"] = False
    node["template"] = dict(template)
    node["outputs"] = [
        out.model_dump()
        for out in component._format_flow_outputs(  # noqa: SLF001
            graph, selected_output=(binding.node_id, binding.output_name)
        )
    ]
    node["description"] = "Builds the agent's instructions from the selected flow."
    registry = {"RunFlow": json.loads(json.dumps(node))}
    added = add_component(flow, "RunFlow", registry)
    generated = flow["data"]["nodes"][-1]
    generated["data"][BINDING_ORIGIN] = origin
    agent = next(node for node in flow["data"]["nodes"] if node["id"] == agent_id)
    agent["data"]["node"]["template"]["system_prompt"]["input_types"] = ["Message", "Text"]
    position = agent.get("position", {})
    generated["position"] = (
        existing[0].get("position", {})
        if existing
        else {"x": position.get("x", 0) - 450, "y": position.get("y", 0) - 300}
    )
    add_connection(flow, added["id"], f"{binding.node_id}~{binding.output_name}", agent_id, "system_prompt")
    return flow["data"]
