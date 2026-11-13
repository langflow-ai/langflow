"""Removing secrets from recorded operations and reconstructed graphs before they leave the server.

Stored operations hold exactly what the flow held, secrets included, so that
replay reproduces the flow. Every read strips them with the scrubber flow
export uses: literal secret values are nulled, while fields bound to a global
variable keep the variable's name, which is not a secret and which playback
needs. Only names of the owner's existing variables are kept.

An ``add_nodes`` payload is whole nodes and is scrubbed like any flow. A
``set_field`` carries only a path and a value, and the field it writes into
decides which parts of the value are secrets. So when the history records a
batch, it scrubs two copies of each written node of the graph after the
batch: one as a flow read scrubs it, and one as if the owner had no
variables. It stores with each write the parts of its value that the
scrubbing changes (``SecretFinder``):

- ``literal``: the first scrubbing set the part to null. A read sets it to
  null.
- ``removed``: the first scrubbing removed the part. A read removes it.
- ``variable``: the first scrubbing kept the part, and the second set it to
  null or removed it, so the part names one of the owner's variables. A read
  keeps it when it still names one of the owner's variables, and sets it to
  null otherwise.

A part's path is relative to the written value: object keys and list
indexes. The stored value never changes, so an index always names the same
item.

A write without such parts has none stored, and a read returns its value as
it is.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from lfx.services.flow_operations import SetNodeFieldUpdate, UpdateNodesOp, load_node_schema

from langflow.utils.flow_secrets import strip_secret_field_values_in_place

if TYPE_CHECKING:
    from collections.abc import Collection

    from lfx.services.flow_operations import FlowOperation, NodeFieldPath

SecretKind = Literal["literal", "removed", "variable"]
SECRET_KINDS: frozenset[str] = frozenset({"literal", "removed", "variable"})
# Object keys and list indexes in a written value.
SecretPath = tuple[str | int, ...]


@dataclass(frozen=True)
class SecretPart:
    """One part of a written value that a read strips.

    ``path`` is relative to the written value: object keys, and list indexes.
    An empty path is the whole value.
    """

    path: SecretPath
    kind: SecretKind

    def to_json(self) -> dict[str, Any]:
        return {"path": list(self.path), "kind": self.kind}

    @classmethod
    def from_json(cls, raw: Any) -> SecretPart:
        """Read one stored part. Raise ``ValueError`` when it is malformed."""
        if not isinstance(raw, dict) or raw.keys() != {"path", "kind"}:
            msg = f"a secret part must be an object with a path and a kind: {raw!r}"
            raise ValueError(msg)
        if raw["kind"] not in SECRET_KINDS:
            msg = f"unknown secret kind {raw['kind']!r}"
            raise ValueError(msg)
        if not isinstance(raw["path"], list):
            msg = f"a secret path must be a list: {raw['path']!r}"
            raise ValueError(msg)  # noqa: TRY004 - the decoder reports every malformed part as one kind of damage
        for segment in raw["path"]:
            is_index = isinstance(segment, int) and not isinstance(segment, bool) and segment >= 0
            if not (isinstance(segment, str) or is_index):
                msg = f"a secret path segment must be an object key or a list index: {segment!r}"
                raise ValueError(msg)
        return cls(path=tuple(raw["path"]), kind=raw["kind"])


# The secret parts of one write. Most writes have none.
WriteSecrets = tuple[SecretPart, ...]
# For an update_nodes, the secret parts of each write, in order. Empty for any other operation.
OperationSecrets = tuple[WriteSecrets, ...]


def strip_graph_secrets(flow_data: dict[str, Any], known_variable_names: Collection[str]) -> dict[str, Any]:
    """Return a copy of a graph with literal secrets removed."""
    stripped = copy.deepcopy(flow_data)
    strip_secret_field_values_in_place(stripped, variable_references=set(), known_variable_names=known_variable_names)
    return stripped


# --- Recording ----------------------------------------------------------------------------


class SecretFinder:
    """Finds the secret parts of the writes of one batch, against the graph after the batch.

    Each written node is scrubbed twice: once as a flow read scrubs it, with
    the names of the owner's variables, and once with no owner variables.
    """

    def __init__(self, graph: dict[str, Any], known_variable_names: Collection[str]) -> None:
        self._nodes_by_id = {node["id"]: node for node in graph["nodes"]}
        self._known_variable_names = known_variable_names
        # Node id -> the copy scrubbed with the owner's variables, and the copy scrubbed without them.
        self._scrubbed: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}

    def secrets_of(self, operation: FlowOperation) -> OperationSecrets:
        """Return the secret parts of each write of an ``update_nodes``, or ``()`` for any other operation."""
        if not isinstance(operation, UpdateNodesOp):
            return ()
        return tuple(
            self._write_secrets(update) if isinstance(update, SetNodeFieldUpdate) else ()
            for update in operation.updates
        )

    def _write_secrets(self, update: SetNodeFieldUpdate) -> WriteSecrets:
        # The diff writes only nodes that the graph after the batch keeps.
        node = self._nodes_by_id[update.id]
        kept, unbound = self._scrub(node)
        steps = _steps(node, update.path)
        written = _follow(node, steps)
        if written is _ABSENT or written != update.value:
            msg = f"node {update.id!r}: the graph after the batch does not hold the value written at {update.path!r}"
            raise ValueError(msg)
        parts: list[SecretPart] = []
        _find_parts(update.id, (), written, _follow(kept, steps), _follow(unbound, steps), parts)
        if any(part.kind == "removed" and not part.path for part in parts):
            msg = f"node {update.id!r}: the secret scrubbing removed the whole value written at {update.path!r}"
            raise ValueError(msg)
        return tuple(parts)

    def _scrub(self, node: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        if node["id"] not in self._scrubbed:
            self._scrubbed[node["id"]] = (
                _scrubbed(node, self._known_variable_names),
                _scrubbed(node, frozenset()),
            )
        return self._scrubbed[node["id"]]


def _scrubbed(node: dict[str, Any], known_variable_names: Collection[str]) -> dict[str, Any]:
    scrubbed = copy.deepcopy(node)
    strip_secret_field_values_in_place(
        {"nodes": [scrubbed]}, variable_references=set(), known_variable_names=known_variable_names
    )
    return scrubbed


# A key the scrubbing removed, or a parent it nulled.
_ABSENT = object()


def _steps(node: dict[str, Any], path: NodeFieldPath) -> list[str | int]:
    """Return the object keys and list indexes that a write's operation path follows in ``node``."""
    steps: list[str | int] = []
    value: Any = node
    for index, segment in enumerate(path):
        if isinstance(segment, str):
            value = value.get(segment) if isinstance(value, dict) else None
            steps.append(segment)
            continue
        keyed = load_node_schema().keyed_list_at(node, tuple(path[:index]))
        if keyed is None or not isinstance(value, list):
            msg = f"node {node['id']!r}: {path!r} selects from a list that is not keyed"
            raise ValueError(msg)
        slot = next((slot for slot, item in enumerate(value) if keyed.key_of(item) == segment.key), None)
        if slot is None:
            msg = f"node {node['id']!r}: {path!r} selects an item the list does not hold"
            raise ValueError(msg)
        steps.append(slot)
        value = value[slot]
    return steps


def _follow(value: Any, steps: list[str | int]) -> Any:
    """Return the value at ``steps``, or ``_ABSENT`` when a step is missing."""
    for step in steps:
        in_object = isinstance(step, str) and isinstance(value, dict) and step in value
        in_list = isinstance(step, int) and isinstance(value, list) and step < len(value)
        if not (in_object or in_list):
            return _ABSENT
        value = value[step]
    return value


def _find_parts(
    node_id: str,
    path: SecretPath,
    written: Any,
    kept: Any,
    unbound: Any,
    parts: list[SecretPart],
) -> None:
    """Add the parts of ``written`` that a read strips.

    ``kept`` is the value scrubbed with the owner's variables, and
    ``unbound`` the value scrubbed without them. The scrubbing only ever sets
    a part to null or removes it, so any other change is a defect, and is
    refused.
    """
    if written == kept == unbound:
        return
    if written != kept and kept is None:
        parts.append(SecretPart(path=path, kind="literal"))
        return
    if kept is _ABSENT:
        parts.append(SecretPart(path=path, kind="removed"))
        return
    if written == kept and (unbound is None or unbound is _ABSENT):
        parts.append(SecretPart(path=path, kind="variable"))
        return
    if all(isinstance(value, dict) for value in (written, kept, unbound)) and _adds_only_nulls(written, kept, unbound):
        for key, child in written.items():
            _find_parts(node_id, (*path, key), child, kept.get(key, _ABSENT), unbound.get(key, _ABSENT), parts)
        return
    if all(isinstance(value, list) and len(value) == len(written) for value in (written, kept, unbound)):
        for index, (item, kept_item, unbound_item) in enumerate(zip(written, kept, unbound, strict=True)):
            _find_parts(node_id, (*path, index), item, kept_item, unbound_item, parts)
        return
    msg = f"node {node_id!r}: the secret scrubbing changed part {list(path)!r} to a value other than null"
    raise ValueError(msg)


def _adds_only_nulls(written: dict[str, Any], *scrubbed: dict[str, Any]) -> bool:
    """Return whether every key the scrubbing added holds null.

    The scrubbing gives a template field without a value a null one. That
    hides nothing, so the part is not a secret.
    """
    return all(value[key] is None for value in scrubbed for key in value.keys() - written.keys())


# --- Reading ------------------------------------------------------------------------------


def check_secret_parts(value: Any, parts: WriteSecrets) -> None:
    """Check that the parts address distinct, separate parts of the written value.

    Raise ``ValueError`` otherwise. No part may lie inside another, so a read
    can strip them in any order, and a ``removed`` part is never the whole
    value, which a read cannot remove.
    """
    if any(part.kind == "removed" and not part.path for part in parts):
        msg = "a removed secret part must be a part of the value, not all of it"
        raise ValueError(msg)
    paths = sorted((part.path for part in parts), key=len)
    for index, path in enumerate(paths):
        _resolve(value, path)
        if any(path[: len(shorter)] == shorter for shorter in paths[:index]):
            msg = f"secret part {list(path)!r} lies inside another part"
            raise ValueError(msg)


def strip_operation_secrets(
    operation: FlowOperation, secrets: OperationSecrets, known_variable_names: Collection[str]
) -> dict[str, Any]:
    """Return a stored operation as a read sends it: secrets stripped, and without its secret parts.

    ``secrets`` holds the parts of each write of an ``update_nodes``. It is
    empty for any other operation.
    """
    stripped = operation.model_dump(mode="json")
    if stripped["type"] == "add_nodes":
        strip_secret_field_values_in_place(
            {"nodes": stripped["nodes"]}, variable_references=set(), known_variable_names=known_variable_names
        )
    elif secrets:
        for update, parts in zip(stripped["updates"], secrets, strict=True):
            for part in parts:
                update["value"] = _strip_part(update["value"], part, known_variable_names)
    return stripped


def _strip_part(value: Any, part: SecretPart, known_variable_names: Collection[str]) -> Any:
    """Strip one part of a written value, and return the value."""
    parent, step, current = _resolve(value, part.path)
    if part.kind == "variable" and isinstance(current, str) and current in known_variable_names:
        return value
    if parent is None:
        return None
    if part.kind == "removed":
        del parent[step]
    else:
        parent[step] = None
    return value


def _resolve(value: Any, path: SecretPath) -> tuple[Any, str | int | None, Any]:
    """Return the container of the part at ``path``, its key or index there, and the part.

    The container is None for the whole value. Raise ``ValueError`` when the
    value holds no part at ``path``.
    """
    parent: Any = None
    step: str | int | None = None
    current = value
    for segment in path:
        parent = current
        in_object = isinstance(segment, str) and isinstance(parent, dict) and segment in parent
        in_list = isinstance(segment, int) and isinstance(parent, list) and 0 <= segment < len(parent)
        if not (in_object or in_list):
            msg = f"the written value holds no part at {list(path)!r}"
            raise ValueError(msg)
        step = segment
        current = parent[step]
    return parent, step, current
