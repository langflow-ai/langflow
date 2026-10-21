"""Normalize source code in exported flow payloads."""

from copy import deepcopy

from lfx.utils.flow_envelope import split_flow_envelope


def normalize_code_for_import(flow: dict) -> dict:
    """Return a copy with exported code lines joined without losing trailing newlines."""
    normalized = deepcopy(flow)
    _, graph = split_flow_envelope(normalized)
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return normalized
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_data = node.get("data")
        if not isinstance(node_data, dict):
            continue
        component = node_data.get("node")
        if not isinstance(component, dict):
            continue
        template = component.get("template")
        if not isinstance(template, dict):
            continue
        for field_data in template.values():
            if not isinstance(field_data, dict) or field_data.get("type") != "code":
                continue
            value = field_data.get("value")
            if isinstance(value, list):
                if not all(isinstance(line, str) for line in value):
                    msg = "Code lines must all be strings"
                    raise ValueError(msg)
                field_data["value"] = "\n".join(value)
    return normalized
