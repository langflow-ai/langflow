"""The strict operation parser of the engine, and the operations it returns.

It accepts exactly the shapes the operation protocol defines, as the Rust
engine's parser does (``lfx::ops::ops``): no unknown keys, no missing
fields, no wrong types, a path that names a list item by its key and never by
its index, and no write that changes a list item's key. Each operation is
parsed before a batch starts, so a malformed operation refuses the batch
before anything is read.

Operations are plain values: ``(kind, payload)`` tuples. An update's path is a
tuple of segments, each an object key (``str``) or a list item key (a
one-element ``tuple``), so a path is hashable and compares by value.
"""

from __future__ import annotations

from typing import Any, NoReturn

from lfx.services.flow_operations.exceptions import FlowOperationValidationError
from lfx.services.flow_operations.schema import NODE_OBJECT_PATHS, load_node_schema

ADD_NODES = "add_nodes"
UPDATE_NODES = "update_nodes"
DELETE_NODES = "delete_nodes"
ADD_EDGES = "add_edges"
DELETE_EDGES = "delete_edges"

_PAYLOAD_KEYS = {
    ADD_NODES: "nodes",
    UPDATE_NODES: "updates",
    DELETE_NODES: "ids",
    ADD_EDGES: "edges",
    DELETE_EDGES: "ids",
}

Segment = str | tuple[str]
Path = tuple[Segment, ...]
Operation = tuple[str, list[Any]]

_SCHEMA = load_node_schema()
_OPERATIONS = "operations"
_PATH = "path"


class FieldUpdate:
    """One ``set_field`` or ``delete_field`` on a node."""

    __slots__ = ("delete", "id", "path", "value")

    def __init__(self, node_id: str, path: Path, value: Any = None, *, delete: bool = False) -> None:
        self.id = node_id
        self.path = path
        self.value = value
        self.delete = delete

    def to_json(self) -> dict[str, Any]:
        path = [segment if segment.__class__ is str else {"key": segment[0]} for segment in self.path]
        if self.delete:
            return {"id": self.id, "path": path, "op": "delete_field"}
        return {"id": self.id, "path": path, "op": "set_field", "value": self.value}


def operation_json(operation: Operation) -> dict[str, Any]:
    """An operation as JSON. The payload is shared, not copied."""
    kind, payload = operation
    if kind == UPDATE_NODES:
        return {"type": kind, "updates": [update.to_json() for update in payload]}
    return {"type": kind, _PAYLOAD_KEYS[kind]: payload}


def path_label(path: Path) -> str:
    """A path as JSON text, for error messages."""
    parts = [
        _json_string(segment) if segment.__class__ is str else '{"key":' + _json_string(segment[0]) + "}"
        for segment in path
    ]
    return "[" + ",".join(parts) + "]"


def _json_string(text: str) -> str:
    from json.encoder import encode_basestring

    return encode_basestring(text)


class _ParseError(Exception):
    """Why a value does not have the expected shape, and where, innermost place first."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
        self.places: list[str | int] = []

    def at(self, place: str | int) -> _ParseError:
        self.places.append(place)
        return self

    def error(self, root: str) -> FlowOperationValidationError:
        location = root
        for place in reversed(self.places):
            location += f"[{place}]" if place.__class__ is int else f".{place}"
        return FlowOperationValidationError(f"{location}: {self.message}")


def _fail(message: str, *places: str | int) -> NoReturn:
    """Raise a ``_ParseError`` at ``places``, innermost first."""
    error = _ParseError(message)
    for place in places:
        error.at(place)
    raise error


def parse_operations(operations: Any) -> list[Operation]:
    """Parse a list of operations. Raises ``FlowOperationValidationError`` naming where it is malformed."""
    try:
        if not isinstance(operations, list):
            _fail("must be a list")
        parsed = []
        for index, operation in enumerate(operations):
            try:
                parsed.append(_operation(operation))
            except _ParseError as error:
                raise error.at(index) from None
    except _ParseError as error:
        raise error.error(_OPERATIONS) from None
    return parsed


def _operation(value: Any) -> Operation:
    if not isinstance(value, dict):
        _fail("must be an object")
    if "type" not in value:
        _fail("type is missing")
    kind = value["type"]
    if not isinstance(kind, str):
        _fail("must be a string", "type")
    payload_key = _PAYLOAD_KEYS.get(kind)
    if payload_key is None:
        _fail(f"unsupported operation type {kind!r}", "type")
    payload: Any = _ABSENT
    for name, item in value.items():
        if name == "type":
            continue
        if name != payload_key:
            _fail(f"unexpected key {name!r}")
        payload = item
    if payload is _ABSENT:
        _fail(f"{payload_key} is missing")
    try:
        if not isinstance(payload, list):
            _fail("must be a list")
        if kind == UPDATE_NODES:
            items: list[Any] = _updates(payload)
        elif kind == ADD_NODES:
            items = _entries(payload, _check_node)
        elif kind == ADD_EDGES:
            items = _entries(payload, _check_edge)
        else:
            items = list(payload)
            for index, item in enumerate(items):
                if not isinstance(item, str):
                    _fail("must be a string", index)
    except _ParseError as error:
        raise error.at(payload_key) from None
    return (kind, items)


_ABSENT = object()


def _entries(payload: list[Any], check) -> list[dict[str, Any]]:
    """Nodes or edges, each with its shape, and no id twice."""
    seen: set[str] = set()
    for index, entry in enumerate(payload):
        try:
            if not isinstance(entry, dict):
                _fail("must be an object")
            check(entry)
        except _ParseError as error:
            raise error.at(index) from None
    for index, entry in enumerate(payload):
        entry_id = entry["id"]
        if entry_id in seen:
            _fail(f"repeats the id {entry_id!r}", "id", index)
        seen.add(entry_id)
    return list(payload)


def _check_node(node: dict[str, Any]) -> None:
    node_id = node.get("id")
    if not isinstance(node_id, str) or not node_id:
        _fail("must be a non-empty string", "id")
    value: Any = node
    for object_path in NODE_OBJECT_PATHS:
        value = value.get(object_path[-1]) if isinstance(value, dict) else None
        if not isinstance(value, dict):
            error = _ParseError(f"must be an object (node {node_id!r})")
            for key in reversed(object_path):
                error.at(key)
            raise error


def _check_edge(edge: dict[str, Any]) -> None:
    for key in ("id", "source", "target"):
        value = edge.get(key)
        if not isinstance(value, str) or not value:
            _fail("must be a non-empty string", key)


def _updates(payload: list[Any]) -> list[FieldUpdate]:
    updates = []
    for index, value in enumerate(payload):
        try:
            updates.append(_update(value))
        except _ParseError as error:
            raise error.at(index) from None
    seen: set[tuple[str, Path]] = set()
    for index, update in enumerate(updates):
        key = (update.id, update.path)
        if key in seen:
            _fail(f"repeats the path {path_label(update.path)} of node {update.id!r}", index)
        seen.add(key)
    return updates


def _update(value: Any) -> FieldUpdate:
    if not isinstance(value, dict):
        _fail("must be an object")
    if "op" not in value:
        _fail("op is missing")
    op = value["op"]
    if op == "set_field" and isinstance(op, str):
        is_set = True
    elif op == "delete_field" and isinstance(op, str):
        is_set = False
    else:
        _fail("must be set_field or delete_field", "op")
    node_id: Any = _ABSENT
    path: Any = _ABSENT
    written: Any = _ABSENT
    for name, item in value.items():
        if name == "op":
            continue
        if name == "id":
            if not isinstance(item, str):
                _fail("must be a string", "id")
            node_id = item
        elif name == "path":
            path = _path(item)
        elif name == "value" and is_set:
            written = item
        else:
            _fail(f"unexpected key {name!r}")
    if node_id is _ABSENT:
        _fail("id is missing")
    if not node_id:
        _fail("must not be empty", "id")
    if path is _ABSENT:
        _fail("path is missing")
    if is_set and written is _ABSENT:
        _fail("value is missing")
    update = FieldUpdate(node_id, path, None if written is _ABSENT else written, delete=not is_set)
    _check_keys_kept(update)
    return update


def _path(value: Any) -> Path:
    try:
        if not isinstance(value, list):
            _fail("must be a list")
        segments: list[Segment] = []
        for index, item in enumerate(value):
            try:
                segments.append(_segment(item))
            except _ParseError as error:
                raise error.at(index) from None
        path = tuple(segments)
        check_node_path(path)
    except _ParseError as error:
        raise error.at(_PATH) from None
    return path


def check_node_path(path: Path) -> None:
    """Refuse a path a field update may not write: empty, the node's id, or a whole node object."""
    if not path:
        _fail("must not be empty")
    if path[0] == "id":
        _fail("cannot change the node's id")
    for object_path in NODE_OBJECT_PATHS:
        if path == object_path:
            _fail(f"cannot write the whole of {'.'.join(object_path)}; write inside it")


def checked_node_path(path: Path) -> Path:
    """``path`` after the checks of ``check_node_path``, which raise ``FlowOperationValidationError``."""
    try:
        check_node_path(path)
    except _ParseError as error:
        raise error.error(_PATH) from None
    return path


_INVALID_SEGMENT = 'must be an object key or {"key": ...} with a non-empty key'


def _segment(value: Any) -> Segment:
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        _fail('integer list indexes are not allowed; name a list item with {"key": ...}')
    if isinstance(value, dict) and len(value) == 1:
        key = value.get("key")
        if isinstance(key, str) and key:
            return (key,)
    _fail(_INVALID_SEGMENT)


def _check_keys_kept(update: FieldUpdate) -> None:
    """Refuse an update that changes the key of a list item on its path: an item's key is its id."""
    path = update.path
    for index, segment in enumerate(path):
        if segment.__class__ is str:
            continue
        key = segment[0]
        inner = path[index + 1 :]
        keyed = _SCHEMA.listed_at(path[:index])
        after = _key_after_write(keyed.key, inner, update)
        if after is _UNTOUCHED or after == key:
            continue
        if not inner:
            _fail(f"a list item written at its key must carry the same key: {key!r}", "value")
        _fail("cannot change a list item's key", "path")


_UNTOUCHED = object()
_KEYLESS = object()


def _key_after_write(key_path: tuple[Any, ...], inner: Path, update: FieldUpdate) -> Any:
    """The item's key after the write, ``_KEYLESS`` when it has none, or ``_UNTOUCHED``."""
    if len(inner) > len(key_path):
        return _UNTOUCHED
    for segment, part in zip(inner, key_path, strict=False):
        if segment.__class__ is not str or part.__class__ is not str or segment != part:
            return _UNTOUCHED
    if update.delete:
        return _UNTOUCHED if not inner else _KEYLESS
    value: Any = update.value
    for part in key_path[len(inner) :]:
        if part.__class__ is str:
            value = value.get(part, _KEYLESS) if isinstance(value, dict) else _KEYLESS
        else:
            value = value[part] if isinstance(value, list) and 0 <= part < len(value) else _KEYLESS
        if value is _KEYLESS:
            return _KEYLESS
    return value if isinstance(value, str) else _KEYLESS
