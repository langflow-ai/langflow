"""Normalize source code in exported flow payloads."""

from collections.abc import Iterator
from copy import deepcopy

from lfx.utils.flow_envelope import split_flow_envelope


def _code_fields(flow: dict) -> Iterator[dict]:
    _, graph = split_flow_envelope(flow)
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return
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
            if isinstance(field_data, dict) and field_data.get("type") == "code":
                yield field_data


def has_code_lines(flow: dict) -> bool:
    """Return whether any code field still stores exported code as a list of lines."""
    return any(isinstance(field_data.get("value"), list) for field_data in _code_fields(flow))


def normalize_code_for_import(flow: dict) -> dict:
    """Return a copy with exported code lines joined without losing trailing newlines."""
    normalized = deepcopy(flow)
    for field_data in _code_fields(normalized):
        value = field_data.get("value")
        if isinstance(value, list):
            if not all(isinstance(line, str) for line in value):
                msg = "Code lines must all be strings"
                raise ValueError(msg)
            field_data["value"] = "\n".join(value)
    return normalized
