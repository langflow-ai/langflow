"""Structural diffing for two serialized flow payloads.

This module is deliberately independent of the API and service layers, mirroring
``flow_secrets``, so a diff can be computed at any boundary without importing
FastAPI.

The security invariant is the reason this runs server-side at all. Callers hand
over both the raw payload and its scrubbed counterpart for each side. Every value
that leaves this module is read from the *scrubbed* payload; the raw payloads are
only ever compared to each other to derive booleans. A field whose scrubbed value
hides the change is reported as ``redacted``, which tells the caller that
something moved without disclosing what it moved to. Rotating an API key is
therefore visible as a change and invisible as a value.

The scrubbed payload is authoritative: if scrubbing failed and produced ``None``
where raw data exists, :func:`compute_flow_diff` raises rather than falling back
to raw.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from typing import Any

# A value longer than this is truncated in the diff, with a flag set. Field values
# are arbitrary user content and a diff is a summary, not an export.
MAX_VALUE_PREVIEW_CHARS = 2000

# Above this, a code field is reported as changed without a line-level diff.
# difflib is O(n*m) and a component can hold a very large module.
MAX_CODE_FIELD_CHARS = 200_000

# Cap on the rendered unified-diff lines kept for a single code field.
MAX_CODE_DIFF_LINES = 400

# Cap on per-node detail objects. Summary counts stay exact past this point.
MAX_MODIFIED_NODE_DETAILS = 200

# Cap on the dotted paths reported for changes outside the template.
MAX_OTHER_CHANGED_KEYS = 50

# Node keys that track canvas interaction rather than flow logic. Dragging a node
# must not register as a change. This is a superset of
# ``langflow.api.utils.core._VOLATILE_NODE_FIELDS``, which covers the narrower
# export-normalisation case; it is restated here rather than imported so this
# module keeps no dependency on the API package.
_VOLATILE_NODE_KEYS = frozenset(
    {
        "dragging",
        "height",
        "measured",
        "position",
        "positionAbsolute",
        "resizing",
        "selected",
        "style",
        "width",
    }
)

# Handled explicitly, so excluded from the generic "what else changed" walk.
_TEMPLATE_KEY = "template"
_DISPLAY_NAME_KEY = "display_name"

_CODE_FIELD_TYPE = "code"

_EMPTY_FLOW: dict[str, list] = {"nodes": [], "edges": []}


class FlowDiffError(ValueError):
    """Base class for errors raised while diffing two flow payloads."""


class FlowDiffStripError(FlowDiffError):
    """Raised when a side carries raw data but its scrubbed counterpart is missing.

    ``strip_version_data`` fails closed and returns ``None`` when scrubbing
    raises. Diffing the raw payload in that case would publish exactly the
    secrets the scrubber could not clear, so the diff is refused instead.
    """


@dataclass(frozen=True)
class FlowDiffSide:
    """One side of a diff, carrying both the raw and the scrubbed payload.

    Holding the pair together is what makes the module's invariant checkable:
    ``raw`` feeds comparisons, ``stripped`` feeds output. Callers must scrub with
    the same scrubber used on every other read path.

    Attributes:
        raw: The unscrubbed flow data, or None when the side has no data.
        stripped: The scrubbed flow data, or None when the side has no data.
    """

    raw: dict | None
    stripped: dict | None

    def validate(self) -> None:
        """Reject a side whose scrubbing failed closed.

        Raises:
            FlowDiffStripError: If raw data exists but the scrubbed payload is None.
        """
        if self.raw is not None and self.stripped is None:
            msg = "Flow data could not be scrubbed for comparison."
            raise FlowDiffStripError(msg)


def _as_flow(data: dict | None) -> dict:
    """Return a payload safe to read nodes and edges from."""
    return data if isinstance(data, dict) else _EMPTY_FLOW


def _node_list(data: dict | None) -> list:
    """Return the node list of a payload, or an empty list when malformed."""
    nodes = _as_flow(data).get("nodes")
    return nodes if isinstance(nodes, list) else []


def _edge_list(data: dict | None) -> list:
    """Return the edge list of a payload, or an empty list when malformed."""
    edges = _as_flow(data).get("edges")
    return edges if isinstance(edges, list) else []


def _node_id(node: Any) -> str | None:
    """Return a node's identifier, falling back to the inner data id."""
    if not isinstance(node, dict):
        return None
    node_id = node.get("id")
    if isinstance(node_id, str) and node_id:
        return node_id
    data = node.get("data")
    if isinstance(data, dict):
        inner = data.get("id")
        if isinstance(inner, str) and inner:
            return inner
    return None


def _index_nodes(nodes: list) -> dict[str, dict]:
    """Index nodes by identifier, skipping malformed entries.

    A duplicate identifier keeps the first occurrence, matching how the runtime
    resolves a vertex by id.
    """
    indexed: dict[str, dict] = {}
    for node in nodes:
        node_id = _node_id(node)
        if node_id is not None and node_id not in indexed:
            indexed[node_id] = node
    return indexed


def _edge_key(edge: Any) -> str | None:
    """Return a stable identity for an edge.

    Langflow edge ids are derived from the four handle components, so a rewired
    edge yields a different key and surfaces as a removal plus an addition. The
    composite fallback keeps that property for payloads written without an id.
    """
    if not isinstance(edge, dict):
        return None
    edge_id = edge.get("id")
    if isinstance(edge_id, str) and edge_id:
        return edge_id
    parts = [edge.get("source"), edge.get("sourceHandle"), edge.get("target"), edge.get("targetHandle")]
    if all(part is None for part in parts):
        return None
    return "|".join("" if part is None else str(part) for part in parts)


def _index_edges(edges: list) -> dict[str, dict]:
    """Index edges by identity, skipping malformed entries."""
    indexed: dict[str, dict] = {}
    for edge in edges:
        key = _edge_key(edge)
        if key is not None and key not in indexed:
            indexed[key] = edge
    return indexed


def _inner_node(node: Any) -> dict:
    """Return the ``data.node`` sub-dict of a node, or an empty dict."""
    if not isinstance(node, dict):
        return {}
    data = node.get("data")
    if not isinstance(data, dict):
        return {}
    inner = data.get("node")
    return inner if isinstance(inner, dict) else {}


def _template(node: Any) -> dict:
    """Return the template dict of a node, or an empty dict."""
    template = _inner_node(node).get(_TEMPLATE_KEY)
    return template if isinstance(template, dict) else {}


def _node_ref(node_id: str, node: Any) -> dict:
    """Build the bounded reference emitted for an added or removed node.

    Only four scalars are exposed. The full node payload is never echoed, which
    keeps the response bounded and the leak surface minimal.
    """
    inner = _inner_node(node)
    data = node.get("data") if isinstance(node, dict) else None
    display_name = inner.get(_DISPLAY_NAME_KEY)
    component_type = data.get("type") if isinstance(data, dict) else None
    node_type = node.get("type") if isinstance(node, dict) else None
    return {
        "id": node_id,
        "display_name": display_name if isinstance(display_name, str) else None,
        "component_type": component_type if isinstance(component_type, str) else None,
        "node_type": node_type if isinstance(node_type, str) else None,
    }


def _edge_ref(key: str, edge: Any) -> dict:
    """Build the reference emitted for an added or removed edge."""
    source = edge.get("source") if isinstance(edge, dict) else None
    target = edge.get("target") if isinstance(edge, dict) else None
    edge_data = edge.get("data") if isinstance(edge, dict) else None
    source_handle_name = None
    target_handle_name = None
    if isinstance(edge_data, dict):
        source_handle = edge_data.get("sourceHandle")
        if isinstance(source_handle, dict):
            name = source_handle.get("name")
            source_handle_name = name if isinstance(name, str) else None
        target_handle = edge_data.get("targetHandle")
        if isinstance(target_handle, dict):
            field_name = target_handle.get("fieldName")
            target_handle_name = field_name if isinstance(field_name, str) else None
    return {
        "id": key,
        "source": source if isinstance(source, str) else None,
        "target": target if isinstance(target, str) else None,
        "source_handle_name": source_handle_name,
        "target_handle_name": target_handle_name,
    }


def _preview_value(value: Any) -> tuple[Any, bool]:
    """Return a bounded rendering of a field value and whether it was truncated.

    Strings are cut at :data:`MAX_VALUE_PREVIEW_CHARS`. Structured values that
    serialise beyond that are replaced by a short type summary rather than a
    partial structure, which would be misleading to diff against.
    """
    if isinstance(value, str):
        if len(value) > MAX_VALUE_PREVIEW_CHARS:
            return value[:MAX_VALUE_PREVIEW_CHARS], True
        return value, False
    if value is None or isinstance(value, (bool, int, float)):
        return value, False
    try:
        encoded = json.dumps(value, default=str)
    except (TypeError, ValueError):
        return f"<unserializable {type(value).__name__}>", True
    if len(encoded) > MAX_VALUE_PREVIEW_CHARS:
        size = len(value) if isinstance(value, (list, dict)) else len(encoded)
        return f"<{type(value).__name__} with {size} entries>", True
    return value, False


def _field_value(template: dict, name: str) -> Any:
    """Return the ``value`` of a template field, or None when absent."""
    field = template.get(name)
    if isinstance(field, dict):
        return field.get("value")
    return None


def _is_field_present(template: dict, name: str) -> bool:
    """Return whether a template holds a well-formed field under this name."""
    return isinstance(template.get(name), dict)


def _is_code_field(*templates_and_names: Any) -> bool:
    """Return whether either side declares this field as a code field."""
    for template, name in templates_and_names:
        field = template.get(name)
        if isinstance(field, dict) and str(field.get("type") or "").lower() == _CODE_FIELD_TYPE:
            return True
    return False


def _field_display_name(*templates_and_names: Any) -> str | None:
    """Return the first display name declared for a field across both sides."""
    for template, name in templates_and_names:
        field = template.get(name)
        if isinstance(field, dict):
            display_name = field.get(_DISPLAY_NAME_KEY)
            if isinstance(display_name, str):
                return display_name
    return None


def _redaction(raw_before: Any, raw_after: Any, stripped_before: Any, stripped_after: Any) -> tuple[bool, bool]:
    """Decide whether a field changed and whether its values must be withheld.

    ``changed`` is computed from the raw values, so a secret rotation is detected
    even though both scrubbed values are None. ``redacted`` is set when the
    scrubber touched either side, or when the scrubbed values cannot express the
    change — the conservative reading in both directions.

    Args:
        raw_before: Unscrubbed value on the base side.
        raw_after: Unscrubbed value on the target side.
        stripped_before: Scrubbed value on the base side.
        stripped_after: Scrubbed value on the target side.

    Returns:
        A ``(changed, redacted)`` pair.
    """
    changed = raw_before != raw_after
    scrubbed = (raw_before != stripped_before) or (raw_after != stripped_after)
    redacted = scrubbed or (changed and stripped_before == stripped_after)
    return changed, redacted


def _code_change(
    name: str,
    display_name: str | None,
    stripped_before: Any,
    stripped_after: Any,
    *,
    redacted: bool,
) -> dict:
    """Build the line-level change record for a code field.

    Rendering the unified diff here means the browser needs no diff library.
    """
    change: dict[str, Any] = {
        "field_name": name,
        "display_name": display_name,
        "added_lines": 0,
        "removed_lines": 0,
        "unified_diff": None,
        "truncated": False,
        "redacted": redacted,
    }
    if redacted:
        return change

    before = stripped_before if isinstance(stripped_before, str) else ""
    after = stripped_after if isinstance(stripped_after, str) else ""
    if len(before) > MAX_CODE_FIELD_CHARS or len(after) > MAX_CODE_FIELD_CHARS:
        change["truncated"] = True
        return change

    diff_lines = list(
        difflib.unified_diff(before.splitlines(), after.splitlines(), fromfile="", tofile="", lineterm="", n=3)
    )
    change["added_lines"] = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    change["removed_lines"] = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
    if len(diff_lines) > MAX_CODE_DIFF_LINES:
        diff_lines = diff_lines[:MAX_CODE_DIFF_LINES]
        change["truncated"] = True
    change["unified_diff"] = "\n".join(diff_lines)
    return change


def _diff_template(base_node: Any, target_node: Any, base_stripped: Any, target_stripped: Any) -> tuple[list, list]:
    """Compare the template fields of one node across both sides.

    Returns:
        A ``(field_changes, code_changes)`` pair.
    """
    raw_base = _template(base_node)
    raw_target = _template(target_node)
    stripped_base = _template(base_stripped)
    stripped_target = _template(target_stripped)

    field_changes: list[dict] = []
    code_changes: list[dict] = []

    names = sorted(set(raw_base) | set(raw_target))
    for name in names:
        present_before = _is_field_present(raw_base, name)
        present_after = _is_field_present(raw_target, name)
        if not present_before and not present_after:
            # A non-dict template entry such as ``_type`` or a stray colour string.
            continue

        raw_before = _field_value(raw_base, name)
        raw_after = _field_value(raw_target, name)
        stripped_before = _field_value(stripped_base, name)
        stripped_after = _field_value(stripped_target, name)

        changed, redacted = _redaction(raw_before, raw_after, stripped_before, stripped_after)
        if present_before and present_after and not changed:
            continue

        display_name = _field_display_name((raw_base, name), (raw_target, name))

        if _is_code_field((raw_base, name), (raw_target, name)):
            code_changes.append(_code_change(name, display_name, stripped_before, stripped_after, redacted=redacted))
            continue

        if not present_before:
            status = "added"
        elif not present_after:
            status = "removed"
        else:
            status = "modified"

        change: dict[str, Any] = {
            "name": name,
            "display_name": display_name,
            "status": status,
            "redacted": redacted,
            "before_truncated": False,
            "after_truncated": False,
        }
        if not redacted:
            if present_before:
                change["before"], change["before_truncated"] = _preview_value(stripped_before)
            if present_after:
                change["after"], change["after_truncated"] = _preview_value(stripped_after)
        field_changes.append(change)

    return field_changes, code_changes


def _prune_for_walk(node: Any) -> dict:
    """Copy a node with volatile keys and separately-reported fields removed."""
    if not isinstance(node, dict):
        return {}
    pruned = {key: value for key, value in node.items() if key not in _VOLATILE_NODE_KEYS}
    data = pruned.get("data")
    if isinstance(data, dict):
        data_copy = dict(data)
        inner = data_copy.get("node")
        if isinstance(inner, dict):
            data_copy["node"] = {
                key: value for key, value in inner.items() if key not in {_TEMPLATE_KEY, _DISPLAY_NAME_KEY}
            }
        pruned["data"] = data_copy
    return pruned


def _walk_changed_keys(before: Any, after: Any, prefix: str, found: list[str]) -> None:
    """Collect dotted paths where two structures differ.

    Recursion stops at the first differing key rather than descending into a
    wholly replaced subtree, which keeps the reported paths meaningful.
    """
    if len(found) >= MAX_OTHER_CHANGED_KEYS:
        return
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in before or key not in after:
                found.append(path)
            else:
                _walk_changed_keys(before[key], after[key], path, found)
            if len(found) >= MAX_OTHER_CHANGED_KEYS:
                return
        return
    if before != after and prefix:
        found.append(prefix)


def _other_changed_keys(base_node: Any, target_node: Any) -> list[str]:
    """Return dotted paths of node changes outside the template and display name."""
    found: list[str] = []
    _walk_changed_keys(_prune_for_walk(base_node), _prune_for_walk(target_node), "", found)
    return found


def _diff_node(node_id: str, base_node: Any, target_node: Any, base_stripped: Any, target_stripped: Any) -> dict | None:
    """Compare one node across both sides, or None when nothing changed."""
    field_changes, code_changes = _diff_template(base_node, target_node, base_stripped, target_stripped)

    base_display = _inner_node(base_stripped).get(_DISPLAY_NAME_KEY)
    target_display = _inner_node(target_stripped).get(_DISPLAY_NAME_KEY)
    display_name_change = None
    if base_display != target_display:
        display_name_change = {
            "before": base_display if isinstance(base_display, str) else None,
            "after": target_display if isinstance(target_display, str) else None,
        }

    other_keys = _other_changed_keys(base_node, target_node)

    if not field_changes and not code_changes and display_name_change is None and not other_keys:
        return None

    ref = _node_ref(node_id, target_node)
    return {
        **ref,
        "display_name_change": display_name_change,
        "field_changes": field_changes,
        "code_changes": code_changes,
        "other_changed_keys": other_keys,
    }


def compute_flow_diff(base: FlowDiffSide, target: FlowDiffSide) -> dict:
    """Diff two flow payloads, withholding every value the scrubber touched.

    Args:
        base: The left-hand side of the comparison.
        target: The right-hand side of the comparison.

    Returns:
        A dict with ``summary``, ``nodes``, ``edges``, ``identical`` and
        ``truncated`` keys, shaped for ``FlowVersionDiffResponse``.

    Raises:
        FlowDiffStripError: If either side carries raw data whose scrubbed
            counterpart is missing.
    """
    base.validate()
    target.validate()

    base_raw_nodes = _index_nodes(_node_list(base.raw))
    target_raw_nodes = _index_nodes(_node_list(target.raw))
    base_stripped_nodes = _index_nodes(_node_list(base.stripped))
    target_stripped_nodes = _index_nodes(_node_list(target.stripped))

    added_ids = sorted(set(target_raw_nodes) - set(base_raw_nodes))
    removed_ids = sorted(set(base_raw_nodes) - set(target_raw_nodes))
    common_ids = sorted(set(base_raw_nodes) & set(target_raw_nodes))

    modified: list[dict] = []
    unchanged_nodes = 0
    for node_id in common_ids:
        change = _diff_node(
            node_id,
            base_raw_nodes[node_id],
            target_raw_nodes[node_id],
            base_stripped_nodes.get(node_id),
            target_stripped_nodes.get(node_id),
        )
        if change is None:
            unchanged_nodes += 1
        else:
            modified.append(change)

    truncated = False
    modified_count = len(modified)
    if modified_count > MAX_MODIFIED_NODE_DETAILS:
        modified = modified[:MAX_MODIFIED_NODE_DETAILS]
        truncated = True

    base_edges = _index_edges(_edge_list(base.raw))
    target_edges = _index_edges(_edge_list(target.raw))
    added_edge_keys = sorted(set(target_edges) - set(base_edges))
    removed_edge_keys = sorted(set(base_edges) - set(target_edges))
    unchanged_edges = len(set(base_edges) & set(target_edges))

    fields_changed = sum(len(change["field_changes"]) for change in modified)
    code_fields_changed = sum(len(change["code_changes"]) for change in modified)
    secrets_changed = sum(
        sum(1 for field in change["field_changes"] if field["redacted"])
        + sum(1 for code in change["code_changes"] if code["redacted"])
        for change in modified
    )

    identical = not added_ids and not removed_ids and modified_count == 0 and not added_edge_keys
    identical = identical and not removed_edge_keys

    return {
        "summary": {
            "nodes_added": len(added_ids),
            "nodes_removed": len(removed_ids),
            "nodes_modified": modified_count,
            "nodes_unchanged": unchanged_nodes,
            "edges_added": len(added_edge_keys),
            "edges_removed": len(removed_edge_keys),
            "edges_unchanged": unchanged_edges,
            "fields_changed": fields_changed,
            "code_fields_changed": code_fields_changed,
            "secrets_changed": secrets_changed,
        },
        "nodes": {
            "added": [_node_ref(node_id, target_stripped_nodes.get(node_id)) for node_id in added_ids],
            "removed": [_node_ref(node_id, base_stripped_nodes.get(node_id)) for node_id in removed_ids],
            "modified": modified,
        },
        "edges": {
            "added": [_edge_ref(key, target_edges[key]) for key in added_edge_keys],
            "removed": [_edge_ref(key, base_edges[key]) for key in removed_edge_keys],
        },
        "identical": identical,
        "truncated": truncated,
    }
