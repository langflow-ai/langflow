"""The rules every stored flow graph follows.

These rules are the flow's write contract. The engine checks them on the graph
it starts from, and the diff checks them on the graph a save asks for. Each
rule has a stable code (``codes.py``) so a refused write can name what is wrong
and where, and each violation says who fixes it: ``repair_flow_data``, or the
client.

Two groups of rules are checked only against the stored graph a write replaces
(``base``), so what is stored stays acceptable until someone touches it:

- table rows: every table value the write adds or changes must have rows with
  a unique ``__id__`` and a numeric ``__pos__``. Their order in the array is not
  state, so it is never checked, and legacy tables without row ids stay valid
  until someone edits them;
- edge rules (``edge_rules.py``): every edge the write adds or rewires must
  carry valid handles that name an output and an input that exist, must not
  take an input that is already taken, and must not touch a note. They are
  the same checks the engine makes when it applies ``add_edges`` and
  ``update_edges``, so validation and apply never disagree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lfx.services.flow_operations.canonical import is_finite_number, is_row_position, values_equal
from lfx.services.flow_operations.codes import GraphViolationCode, resolution_of
from lfx.services.flow_operations.edge_rules import check_edge, edge_changed, outputs_by_name, read_handles
from lfx.services.flow_operations.exceptions import FlowDataValidationError, FlowOperationValidationError
from lfx.services.flow_operations.schema import load_node_schema
from lfx.services.flow_operations.state import NODE_OBJECT_PATHS, index_graph, require_node_objects

GraphPath = tuple[str | int, ...]


@dataclass(frozen=True)
class GraphViolation:
    """One broken rule, where it was found, and a message without graph values.

    An edge rule violation also names its edge, so a client can fix that edge
    without counting its way through the edge list.
    """

    code: GraphViolationCode
    path: GraphPath
    message: str
    edge_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "code": self.code.value,
            "path": list(self.path),
            "message": self.message,
            "resolution": resolution_of(self.code).value,
        }
        if self.edge_id is not None:
            result["edge_id"] = self.edge_id
        return result


def find_graph_violations(
    flow_data: Any,
    *,
    check_values: bool = True,
    base: Any = None,
) -> list[GraphViolation]:
    """Return every rule ``flow_data`` breaks, in document order.

    ``check_values`` also walks every value for NaN, Infinity and integers too
    large for a double, which JavaScript reads as Infinity. The engine
    skips it when replaying stored operations, whose values were checked when
    they were written, so replay stays proportional to the number of nodes and
    edges rather than to the size of the flow.

    ``base`` is the stored graph a write replaces. When it is given, every
    table value ``flow_data`` adds or changes relative to it is checked too,
    and so is every edge it adds or rewires, once the graph's structure is
    sound; pass an empty graph for a flow that has no stored graph yet.

    ``base`` itself is not validated, but the edge rules read the template and
    outputs of every node of ``base`` that ``flow_data`` keeps: when such a node
    lacks ``data``, ``data.node`` or ``data.node.template`` as an object, this
    raises ``FlowOperationValidationError``.
    """
    if not isinstance(flow_data, dict):
        return [GraphViolation(GraphViolationCode.FLOW_DATA_NOT_OBJECT, (), "flow data must be an object")]

    violations: list[GraphViolation] = []
    nodes = flow_data.get("nodes")
    edges = flow_data.get("edges")
    for key, collection in (("nodes", nodes), ("edges", edges)):
        if not isinstance(collection, list):
            violations.append(
                GraphViolation(GraphViolationCode.COLLECTION_NOT_LIST, (key,), f"flow data {key} must be a list")
            )

    node_ids: set[str] = set()
    if isinstance(nodes, list):
        for index, node in enumerate(nodes):
            violations.extend(_node_violations(node, ("nodes", index), node_ids))

    if isinstance(edges, list):
        edge_ids: set[str] = set()
        for index, edge in enumerate(edges):
            violations.extend(_edge_violations(edge, ("edges", index), edge_ids, node_ids))

    if base is not None and isinstance(nodes, list):
        structural = not violations
        violations.extend(find_table_violations(base, flow_data))
        if structural:
            violations.extend(find_edge_violations(base, flow_data))
    if check_values:
        violations.extend(_non_finite_violations(flow_data))
    return violations


def validate_flow_data(
    flow_data: Any,
    *,
    check_values: bool = True,
    context: str = "flow.data",
    base: Any = None,
) -> None:
    """Raise ``FlowDataValidationError`` listing every violation, if there are any."""
    violations = find_graph_violations(flow_data, check_values=check_values, base=base)
    if violations:
        first = violations[0]
        location = ".".join(str(part) for part in first.path) or "<root>"
        more = f" (and {len(violations) - 1} more)" if len(violations) > 1 else ""
        msg = f"{context}: {first.message} at {location}{more}"
        raise FlowDataValidationError(msg, violations=violations)


def _node_violations(node: Any, path: GraphPath, node_ids: set[str]) -> list[GraphViolation]:
    if not isinstance(node, dict):
        return [GraphViolation(GraphViolationCode.NODE_NOT_OBJECT, path, "node must be an object")]

    violations: list[GraphViolation] = []
    node_id = node.get("id")
    if not isinstance(node_id, str) or not node_id:
        violations.append(
            GraphViolation(GraphViolationCode.NODE_ID_MISSING, (*path, "id"), "node must have a non-empty string id")
        )
    elif node_id in node_ids:
        violations.append(GraphViolation(GraphViolationCode.NODE_ID_DUPLICATE, (*path, "id"), "duplicate node id"))
    else:
        node_ids.add(node_id)

    value: Any = node
    for object_path in NODE_OBJECT_PATHS:
        value = value.get(object_path[-1]) if isinstance(value, dict) else None
        if not isinstance(value, dict):
            label = ".".join(str(part) for part in object_path)
            violations.append(
                GraphViolation(
                    GraphViolationCode.NODE_DATA_NOT_OBJECT, (*path, *object_path), f"{label} must be an object"
                )
            )
            break
    return violations


def _edge_violations(edge: Any, path: GraphPath, edge_ids: set[str], node_ids: set[str]) -> list[GraphViolation]:
    if not isinstance(edge, dict):
        return [GraphViolation(GraphViolationCode.EDGE_NOT_OBJECT, path, "edge must be an object")]

    violations: list[GraphViolation] = []
    edge_id = edge.get("id")
    if not isinstance(edge_id, str) or not edge_id:
        violations.append(
            GraphViolation(GraphViolationCode.EDGE_ID_MISSING, (*path, "id"), "edge must have a non-empty string id")
        )
    elif edge_id in edge_ids:
        violations.append(GraphViolation(GraphViolationCode.EDGE_ID_DUPLICATE, (*path, "id"), "duplicate edge id"))
    else:
        edge_ids.add(edge_id)

    for endpoint in ("source", "target"):
        node_id = edge.get(endpoint)
        if not isinstance(node_id, str) or not node_id:
            message = f"edge must have a non-empty string {endpoint}"
        elif node_id not in node_ids:
            message = f"edge {endpoint} node does not exist"
        else:
            continue
        violations.append(GraphViolation(GraphViolationCode.EDGE_ENDPOINT_INVALID, (*path, endpoint), message))
    return violations


def _non_finite_violations(flow_data: dict[str, Any]) -> list[GraphViolation]:
    violations: list[GraphViolation] = []
    stack: list[tuple[Any, GraphPath]] = [(flow_data, ())]
    while stack:
        value, path = stack.pop()
        if isinstance(value, (int, float)) and not is_finite_number(value):
            violations.append(
                GraphViolation(
                    GraphViolationCode.NON_FINITE_NUMBER,
                    path,
                    "NaN, Infinity and integers too large for a double are not valid JSON",
                )
            )
        elif isinstance(value, dict):
            stack.extend((item, (*path, key)) for key, item in reversed(value.items()))
        elif isinstance(value, list):
            stack.extend((item, (*path, index)) for index, item in reversed(list(enumerate(value))))
    return violations


# --- Edges a write adds or rewires ----------------------------------------------------


def changed_edges(base: Any, target: dict[str, Any]) -> list[int]:
    """Return the indexes of the edges ``target`` adds relative to ``base``, and of the edges it cuts.

    Added edges are new edges, and edges that changed (``edge_changed``),
    which a write deletes and adds again. A cut edge is one ``target`` keeps
    unchanged while it removes the template field or output at one of its
    ends. Applying that removal deletes the edge, so a target that keeps it
    can never be replayed. ``target`` must be structurally sound, and each
    node of ``base`` it keeps must carry its node objects
    (``FlowOperationValidationError`` otherwise).
    """
    stored = {edge["id"]: edge for edge in _list(base, "edges") if isinstance(edge, dict) and "id" in edge}
    removed = _removed_ends(base, target)
    changed: list[int] = []
    for index, edge in enumerate(target["edges"]):
        before = stored.get(edge["id"])
        if before is None or edge_changed(before, edge) or _is_cut(edge, removed):
            changed.append(index)
    return changed


def remove_cut_edges(base: Any, target: dict[str, Any]) -> list[str]:
    """Remove from ``target``, in place, the edges it keeps but cuts, and return their ids.

    This is what a writer that is not the editor (the assistant, the MCP
    server) does before saving, as the editor's ``cleanEdges`` does: a write
    that removes a field or an output also removes the edges at it, so the
    save passes the edge rules. ``base`` is the stored graph, which is sound.
    A ``target`` that is not structurally sound is left as it is: the save
    refuses it with its violations.
    """
    if find_graph_violations(target, check_values=False):
        return []
    removed = _removed_ends(base, target)
    if not removed:
        return []
    kept: list[dict[str, Any]] = []
    cut: list[str] = []
    stored = {edge["id"] for edge in _list(base, "edges") if isinstance(edge, dict) and "id" in edge}
    for edge in target["edges"]:
        if edge["id"] in stored and _is_cut(edge, removed):
            cut.append(edge["id"])
        else:
            kept.append(edge)
    target["edges"] = kept
    return cut


@dataclass
class _RemovedEnds:
    """The template fields and outputs a write removes from one node."""

    fields: set[str]
    outputs: set[str]


def _removed_ends(base: Any, target: dict[str, Any]) -> dict[str, _RemovedEnds]:
    """Return, by node id, the template fields and outputs ``target`` removes from nodes it keeps."""
    base_nodes = {node["id"]: node for node in _list(base, "nodes") if isinstance(node, dict) and "id" in node}
    removed: dict[str, _RemovedEnds] = {}
    for node in target["nodes"]:
        stored = base_nodes.get(node["id"])
        if stored is None:
            continue
        require_node_objects(stored, context=f"stored node {node['id']!r}")
        before, after = stored["data"]["node"], node["data"]["node"]
        fields = before["template"].keys() - after["template"].keys()
        outputs: set[str] = set()
        if "outputs" in before and not values_equal(before["outputs"], after.get("outputs")):
            outputs = set(outputs_by_name(before["outputs"], node_id=node["id"]))
            if "outputs" in after:
                outputs -= set(outputs_by_name(after["outputs"], node_id=node["id"]))
        if fields or outputs:
            removed[node["id"]] = _RemovedEnds(fields=set(fields), outputs=outputs)
    return removed


def _is_cut(edge: dict[str, Any], removed: dict[str, _RemovedEnds]) -> bool:
    """Return whether a kept edge leaves from or enters a field or output the write removes.

    Applying the removal reads the handles of every edge at that node
    strictly, so an edge there whose handles cannot be read counts too, and
    the edge rules report it.
    """
    source, target = removed.get(edge["source"]), removed.get(edge["target"])
    if source is None and target is None:
        return False
    try:
        handles = read_handles(edge)
    except FlowOperationValidationError:
        return True
    if source is not None and handles.output in source.outputs:
        return True
    if target is None:
        return False
    kind, name = handles.input
    return name in (target.fields if kind == "field" else target.outputs)


def find_edge_violations(base: Any, target: dict[str, Any]) -> list[GraphViolation]:
    """Return the edge rules broken by the edges ``target`` adds, rewires or cuts relative to ``base``.

    ``target`` must be structurally sound: unique ids, and edges whose
    endpoints exist.
    """
    indexes = changed_edges(base, target)
    if not indexes:
        return []
    state = index_graph(target)
    edges = target["edges"]
    index_of = {edge["id"]: index for index, edge in enumerate(edges)}
    # Checking one edge reads the other edges into its input, so it can fail on
    # one of them: each violation is reported once, at the edge that broke the rule.
    violations: dict[str, GraphViolation] = {}
    for index in indexes:
        try:
            check_edge(state, edges[index])
        except FlowOperationValidationError as error:
            if error.edge_id is None:
                raise
            if error.edge_id not in violations:
                violations[error.edge_id] = GraphViolation(
                    GraphViolationCode(error.code), ("edges", index_of[error.edge_id]), str(error), error.edge_id
                )
    return sorted(violations.values(), key=lambda violation: violation.path[1])


# --- Table rows ------------------------------------------------------------------------


@dataclass(frozen=True)
class ChangedTable:
    """A table value a write adds or changes, and where it is."""

    path: GraphPath
    rows: list[Any]


def changed_tables(base: Any, target: dict[str, Any]) -> list[ChangedTable]:
    """Return the table values ``target`` adds or changes relative to ``base``, in document order."""
    schema = load_node_schema()
    base_templates: dict[str, dict[str, Any]] = {}
    for node in _list(base, "nodes"):
        template = _template(node)
        if template is not None and isinstance(node.get("id"), str):
            base_templates.setdefault(node["id"], template)

    tables: list[ChangedTable] = []
    for index, node in enumerate(_list(target, "nodes")):
        template = _template(node)
        if template is None:
            continue
        stored = base_templates.get(node.get("id")) or {}
        for field_name, field in template.items():
            value_path = ("data", "node", "template", field_name, "value")
            # Only tables: a natural-key list (tool actions) is not one, even under a table-typed field.
            if schema.keyed_list_at(node, value_path) is not schema.table or not isinstance(field.get("value"), list):
                continue
            stored_field = stored.get(field_name)
            if (
                isinstance(stored_field, dict)
                and "value" in stored_field
                and values_equal(stored_field["value"], field["value"])
            ):
                continue
            tables.append(ChangedTable(path=("nodes", index, *value_path), rows=field["value"]))
    return tables


def find_table_violations(base: Any, target: Any) -> list[GraphViolation]:
    """Return the row rules broken by table values ``target`` adds or changes relative to ``base``."""
    violations: list[GraphViolation] = []
    for table in changed_tables(base, target):
        violations.extend(table_row_violations(table.rows, table.path))
    return violations


def table_row_violations(rows: list[Any], path: GraphPath) -> list[GraphViolation]:
    """Return the row rules one table value breaks."""
    table = load_node_schema().table
    id_key, position_key = table.key[0], table.position
    violations: list[GraphViolation] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            violations.append(
                GraphViolation(GraphViolationCode.TABLE_ROW_NOT_OBJECT, (*path, index), "table row must be an object")
            )
            continue
        row_id = row.get(id_key)
        if not isinstance(row_id, str) or not row_id:
            violations.append(
                GraphViolation(
                    GraphViolationCode.TABLE_ROW_ID_MISSING,
                    (*path, index, id_key),
                    f"table row must have a non-empty string {id_key}",
                )
            )
        elif row_id in seen_ids:
            violations.append(
                GraphViolation(GraphViolationCode.TABLE_ROW_ID_DUPLICATE, (*path, index, id_key), "duplicate row id")
            )
        else:
            seen_ids.add(row_id)
        if not is_row_position(row.get(position_key)):
            violations.append(
                GraphViolation(
                    GraphViolationCode.TABLE_ROW_POS_INVALID,
                    (*path, index, position_key),
                    f"table row must have a finite numeric {position_key}",
                )
            )
    return violations


def _list(graph: Any, key: str) -> list[Any]:
    value = graph.get(key) if isinstance(graph, dict) else None
    return value if isinstance(value, list) else []


def _template(node: Any) -> dict[str, Any] | None:
    value: Any = node
    for key in ("data", "node", "template"):
        value = value.get(key) if isinstance(value, dict) else None
    if not isinstance(value, dict):
        return None
    return {name: field for name, field in value.items() if isinstance(field, dict)}
