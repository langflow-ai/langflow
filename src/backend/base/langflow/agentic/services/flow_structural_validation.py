"""Structural (no-execution) validation of a built flow.

A cyclic loop flow can't be run to completion for verification without
risking a hang, so it is validated STRUCTURALLY instead: every required
input is connected or set, the loop has a data source feeding its
``Inputs``, the loop body forms a closed cycle back to the loop port, and
no node is left orphaned. The checks are pure and edge-shape based (no
component registry, no server, no network) so they run identically in the
server, the API path, and from ``lfx``.

Returns human-readable issue strings naming the offending component and
field so the agent can repair the exact wiring in a single fix turn.
"""

from __future__ import annotations

from typing import Any

_EMPTY_VALUES: tuple[Any, ...] = (None, "", [], {})

FLOW_STRUCTURE_RETRY_TEMPLATE = """The loop flow you just built is structurally incomplete \
(it was validated, not run):

{error}

Fix the wiring so every required input is connected: give the Loop a data source into its \
Inputs, connect each component's required inputs, and close the loop body back into the Loop's \
Item input. Then rebuild the flow with the build tool. Do not just describe the fix — apply it."""


def _nodes(flow: dict) -> list[dict]:
    return (flow or {}).get("data", {}).get("nodes", []) or []


def _edges(flow: dict) -> list[dict]:
    return (flow or {}).get("data", {}).get("edges", []) or []


def _node_id(node: dict) -> str:
    return str(node.get("data", {}).get("id", node.get("id", "")))


def _display_name(node: dict) -> str:
    inner = node.get("data", {}).get("node", {})
    return str(inner.get("display_name") or node.get("data", {}).get("type") or _node_id(node))


def _target_handle(edge: dict) -> dict:
    handle = (edge.get("data") or {}).get("targetHandle")
    return handle if isinstance(handle, dict) else {}


def _source_handle(edge: dict) -> dict:
    handle = (edge.get("data") or {}).get("sourceHandle")
    return handle if isinstance(handle, dict) else {}


def _is_loop_feedback_edge(edge: dict) -> bool:
    """Output-shaped targetHandle (``name`` present, ``fieldName`` absent)."""
    handle = _target_handle(edge)
    return "name" in handle and "fieldName" not in handle


def _allows_loop_output_names(node: dict) -> set[str]:
    outputs = node.get("data", {}).get("node", {}).get("outputs", []) or []
    return {o.get("name") for o in outputs if isinstance(o, dict) and o.get("allows_loop") and o.get("name")}


def _loop_port_names(node_id: str, node: dict, edges: list[dict]) -> set[str]:
    """Names of the loop's feedback ports (``item``), from outputs AND feedback edges.

    Registry-independent: even when a node's outputs are not serialized, a
    feedback edge targeting the node reveals the port name it uses.
    """
    ports = _allows_loop_output_names(node)
    for edge in edges:
        if edge.get("target") == node_id and _is_loop_feedback_edge(edge):
            name = _target_handle(edge).get("name")
            if name:
                ports.add(name)
    return ports


def _loop_node_ids(nodes: list[dict], edges: list[dict]) -> list[str]:
    """A node is a loop if it exposes an ``allows_loop`` output OR receives a feedback edge."""
    loop_ids: list[str] = []
    feedback_targets = {e.get("target") for e in edges if _is_loop_feedback_edge(e)}
    for node in nodes:
        nid = _node_id(node)
        if _allows_loop_output_names(node) or nid in feedback_targets:
            loop_ids.append(nid)
    return loop_ids


def _required_input_failures(nodes: list[dict], connected_fields: set[tuple[str, str]]) -> list[str]:
    """Flag required connectable inputs that are neither connected nor set."""
    failures: list[str] = []
    for node in nodes:
        nid = _node_id(node)
        template = node.get("data", {}).get("node", {}).get("template", {}) or {}
        for field_name, field in template.items():
            if not isinstance(field, dict):
                continue
            input_types = field.get("input_types")
            # Only visible, required, connectable handles must be satisfied;
            # hidden/advanced or value-only fields are the component's concern.
            if not field.get("required") or not input_types:
                continue
            if field.get("advanced") or field.get("show") is False:
                continue
            if (nid, field_name) in connected_fields:
                continue
            if field.get("value") not in _EMPTY_VALUES:
                continue
            label = field.get("display_name") or field_name
            failures.append(
                f"{_display_name(node)} is missing a required input: '{label}' is neither connected nor set."
            )
    return failures


def _loop_failures(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Flag loops without a data source or without a closed body cycle."""
    failures: list[str] = []
    by_id = {_node_id(n): n for n in nodes}
    for loop_id in _loop_node_ids(nodes, edges):
        node = by_id.get(loop_id, {})
        name = _display_name(node)
        ports = _loop_port_names(loop_id, node, edges)

        has_data_source = any(
            e.get("target") == loop_id and not _is_loop_feedback_edge(e) and _target_handle(e).get("fieldName")
            for e in edges
        )
        if not has_data_source:
            failures.append(
                f"{name} (Loop) has no data source: its 'Inputs' is not connected. "
                "Add a component (e.g. a Chat Input) feeding the loop."
            )

        item_consumed = any(e.get("source") == loop_id and _source_handle(e).get("name") in ports for e in edges)
        feedback_returned = any(
            e.get("target") == loop_id and _is_loop_feedback_edge(e) and _target_handle(e).get("name") in ports
            for e in edges
        )
        if not item_consumed:
            failures.append(f"{name} (Loop) body never starts: nothing consumes its 'Item' output.")
        elif not feedback_returned:
            failures.append(f"{name} (Loop) body is not a closed cycle: nothing feeds back into its 'Item' input.")
    return failures


def _orphan_failures(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Flag nodes with no connections at all (only meaningful in multi-node flows)."""
    if len(nodes) <= 1:
        return []
    connected: set[str] = set()
    for edge in edges:
        if edge.get("source"):
            connected.add(edge["source"])
        if edge.get("target"):
            connected.add(edge["target"])
    return [
        f"{_display_name(n)} is disconnected — it has no connections." for n in nodes if _node_id(n) not in connected
    ]


def structural_failures(flow: dict) -> list[str]:
    """Return structured wiring failures for a built flow (empty list = structurally sound).

    Checks, in order: required inputs connected-or-set, loop data source +
    closed body cycle, and orphan nodes. Deterministic and side-effect free.
    """
    nodes = _nodes(flow)
    if not nodes:
        return []
    edges = _edges(flow)
    connected_fields: set[tuple[str, str]] = set()
    for edge in edges:
        field_name = _target_handle(edge).get("fieldName")
        if edge.get("target") and field_name:
            connected_fields.add((edge["target"], field_name))

    failures = _required_input_failures(nodes, connected_fields)
    failures.extend(_loop_failures(nodes, edges))
    failures.extend(_orphan_failures(nodes, edges))
    return failures
