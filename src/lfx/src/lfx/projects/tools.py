"""Compose a harness's local tools as ordinary, visible Run Flow nodes."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from lfx.components.flow_controls.run_flow import RunFlowComponent
from lfx.graph.flow_builder import add_component, add_connection, remove_component
from lfx.graph.graph.base import Graph
from lfx.schema.dotdict import dotdict

TOOL_ORIGIN = "_harness_tool"
TOOL_COLUMN_OFFSET = 450
TOOL_WIDTH = 400
TOOL_ROW_HEIGHT = 300


def agent_node_ids(data: dict | None) -> list[str]:
    """Agents whose inputs the harness can configure, without evaluating stored code."""
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), list):
        return []
    return [
        node["id"]
        for node in data["nodes"]
        if isinstance(node, dict)
        and isinstance(node.get("id"), str)
        and isinstance(node.get("data"), dict)
        and node["data"].get("type") == "Agent"
    ]


def validate_tool_flow(target: dict) -> Graph:
    """Validate the Tool adapter contract without running saved component code.

    The caller supplies an authorized flow row. Parsing templates here does not run target
    component constructors, execute the flow, or make an HTTP call back into Langflow.
    """
    graph = Graph.from_payload(
        payload=deepcopy(target["data"]),
        flow_id=target["id"],
        flow_name=target["name"],
        instantiate_components=False,
        emit_extension_events=False,
    )
    component = RunFlowComponent()
    fields = component.get_new_fields_from_graph(graph)
    if not any(field.get("tool_mode") for field in fields):
        msg = f"Flow {target['name']!r} needs an exposed input before it can be used as a tool."
        raise ValueError(msg)
    if not any(vertex.is_output for vertex in graph.vertices):
        msg = f"Flow {target['name']!r} needs an output before it can be used as a tool."
        raise ValueError(msg)
    return graph


def prepare_tool_template(target: dict) -> dict:
    """Use Run Flow's component update to expose a statically validated target's inputs."""
    graph = validate_tool_flow(target)
    component = RunFlowComponent()

    frontend = component.to_frontend_node()
    node = frontend.get("data", frontend)["node"]
    template = dotdict(node["template"])
    metadata = {"id": target["id"], "updated_at": target.get("updated_at")}
    template["flow_name_selected"].update(
        value=target["name"], options=[target["name"]], options_metadata=[metadata], selected_metadata=metadata
    )
    template["flow_id_selected"]["value"] = target["id"]
    # This is the same in-process update called by RunFlow.load_graph_and_update_cfg.
    component.update_build_config_from_graph(template, graph)
    for entry in template.values():
        # File widgets serialize "no files" as a list. A fresh component template still
        # carries "", which Run Flow would otherwise turn into an invalid empty file path.
        if isinstance(entry, dict) and entry.get("type") == "file" and entry.get("value") in (None, ""):
            entry["value"] = []
    node["template"] = dict(template)
    node["field_order"] = [key for key in template if key not in {"code", "_type"}]
    node["add_tool_output"] = True
    node["description"] = f"Runs {target['name']} as a tool for this agent."
    # Run Flow emits dotdict fields; hand the builder ordinary serialized template data.
    return json.loads(json.dumps(node))


def compose_tools(data: dict, *, project_id: str, agent_id: str, targets: list[dict]) -> dict:
    """Reconcile only this project's generated nodes; preserve all hand-authored graph data.

    Existing tool nodes retain their ids, layout, and canvas configuration. Deselecting a tool
    removes its generated node and edges. Running this twice with the same selection is a no-op.
    """
    flow = {"data": deepcopy(data)}
    picked = {target["id"] for target in targets}
    existing = {}
    for node in list(flow["data"]["nodes"]):
        origin = node.get("data", {}).get(TOOL_ORIGIN)
        if not isinstance(origin, dict) or origin.get("project_id") != project_id:
            continue
        target_id = origin.get("flow_id")
        if target_id not in picked:
            remove_component(flow, node["id"])
        else:
            existing[target_id] = node

    agent = next(node for node in flow["data"]["nodes"] if node["id"] == agent_id)
    position = agent.get("position", {"x": 0, "y": 0})
    occupied = [node.get("position", {}) for node in flow["data"]["nodes"]]
    for target in targets:
        binding = target.get("tool_pack")
        if target["id"] in existing:
            node = existing[target["id"]]
            origin = node["data"][TOOL_ORIGIN]
            if origin.get("tool_pack") != binding:
                if origin.get("applied_revision") != _tool_node_revision(node):
                    msg = (
                        "This tool was edited on the canvas. "
                        "Restore it or remove its selection before updating the pack."
                    )
                    raise ValueError(msg)
                registry = {"RunFlow": prepare_tool_template(target)}
                replacement = {"data": {"nodes": [deepcopy(agent)], "edges": []}}
                add_component(replacement, "RunFlow", registry, component_id=node["id"])
                add_connection(replacement, node["id"], "component_as_tool", agent_id, "tools", registry=registry)
                node["data"]["node"] = replacement["data"]["nodes"][-1]["data"]["node"]
                origin["tool_pack"] = binding
                origin["applied_revision"] = _tool_node_revision(node)
            # A manually edited tool stays edited when its reviewed definition is unchanged.
            continue
        registry = {"RunFlow": prepare_tool_template(target)}
        added = add_component(flow, "RunFlow", registry)
        node = flow["data"]["nodes"][-1]
        node["data"][TOOL_ORIGIN] = {"project_id": project_id, "flow_id": target["id"]}
        if binding is not None:
            node["data"][TOOL_ORIGIN]["tool_pack"] = binding
        x, y = position.get("x", 0) - TOOL_COLUMN_OFFSET, position.get("y", 0)
        while any(
            abs(x - other.get("x", 0)) < TOOL_WIDTH and abs(y - other.get("y", 0)) < TOOL_ROW_HEIGHT
            for other in occupied
        ):
            y += TOOL_ROW_HEIGHT
        node["position"] = {"x": x, "y": y}
        occupied.append(node["position"])
        add_connection(flow, added["id"], "component_as_tool", agent_id, "tools", registry=registry)
        if binding is not None:
            node["data"][TOOL_ORIGIN]["applied_revision"] = _tool_node_revision(node)
    return flow["data"]


def _tool_node_revision(node: dict) -> str:
    """Ignore layout while protecting the generated adapter's canvas configuration."""
    definition = dict(node["data"]["node"])
    # The canvas adds this marker when opening an otherwise unchanged node.
    definition.pop("lf_version", None)
    return hashlib.sha256(json.dumps(definition, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
