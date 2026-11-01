"""The node schema: where the units, view state and keyed lists of a flow are.

``node_schema.json`` is the single description of where things are in a node,
so no code hard-codes those paths. The Rust engine embeds a byte-identical
copy. This module loads it once and answers the questions the engine asks
while walking a path.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Callable

NODE_SCHEMA_PATH = Path(__file__).with_name("node_schema.json")
WILDCARD = "*"

SchemaPath = tuple[str, ...]
KeyPath = tuple[str | int, ...]

TEMPLATE_PATH: SchemaPath = ("data", "node", "template")
OUTPUTS_PATH: SchemaPath = ("data", "node", "outputs")
# The objects every node carries for its whole lifetime: data, data.node and data.node.template.
NODE_OBJECT_PATHS: tuple[SchemaPath, ...] = (("data",), ("data", "node"), TEMPLATE_PATH)

# The smallest integer that rounds past the largest double. JavaScript reads
# it, and every larger one, as Infinity, so it is not a finite JSON number.
DOUBLE_OVERFLOW = 2**1024 - 2**970


def field_value_path(field: str) -> SchemaPath:
    """The path of a template field's value."""
    return ("data", "node", "template", field, "value")


def is_finite_number(value: float) -> bool:
    """Return whether a JSON number is finite as the double JavaScript reads it.

    An integer too large for a double reads as Infinity, so it is not finite.
    """
    if isinstance(value, int):
        return -DOUBLE_OVERFLOW < value < DOUBLE_OVERFLOW
    return math.isfinite(value)


def is_row_position(value: Any) -> bool:
    """Return whether ``value`` is a valid keyed list position: a finite number, not a bool."""
    cls = value.__class__
    if cls is float:
        return value - value == 0.0
    if cls is int:
        return -DOUBLE_OVERFLOW < value < DOUBLE_OVERFLOW
    return cls is not bool and isinstance(value, (int, float)) and is_finite_number(value)


@dataclass(frozen=True)
class KeyedList:
    """A list whose items are addressed by a key instead of an index.

    Items of every kind are selected with ``{"key": ...}``: an output by its
    ``name``, a tool action by its first tag, a table row by its ``__id__``.
    Every keyed list is ordered by its items' numeric ``position``, then key;
    its array order is not state.
    """

    kind: Literal["natural", "table"]
    key: KeyPath
    position: str = "__pos__"

    def key_of(self, item: Any) -> str | None:
        """Return an item's key, or None when the item has no string key."""
        value: Any = item
        for part in self.key:
            if part.__class__ is str:
                if not isinstance(value, dict):
                    return None
                value = value.get(part)
            elif isinstance(value, list) and 0 <= part < len(value):
                value = value[part]
            else:
                return None
        return value if isinstance(value, str) else None

    def has_position(self, item: Any) -> bool:
        """Whether an item carries a finite number as its position."""
        return isinstance(item, dict) and self.position in item and is_row_position(item[self.position])


_MISSING = object()


@dataclass(frozen=True)
class NodeSchema:
    version: int
    # The top-level flow keys that are not view state. Every other top-level key is.
    flow_graph_keys: frozenset[str]
    node_view_state: frozenset[str]
    node_view_state_paths: tuple[SchemaPath, ...]
    template_view_state: frozenset[str]
    field_view_state: frozenset[str]
    edge_view_state: frozenset[str]
    value_unit: tuple[str, ...]
    toggles: tuple[str, ...]
    # Node paths the diff splits into their keys; any other value is written whole.
    recursed_paths: frozenset[SchemaPath]
    natural_lists: tuple[tuple[SchemaPath, KeyedList], ...]
    table_path: SchemaPath
    table_when_field: tuple[dict[str, Any], ...]
    table: KeyedList

    @property
    def node_data_view_state(self) -> frozenset[str]:
        """Keys of ``data.node`` that are view state."""
        return frozenset(path[-1] for path in self.node_view_state_paths if path[:-1] == ("data", "node"))

    def is_flow_view_state(self, key: str) -> bool:
        """Return whether a top-level flow key is view state."""
        return key not in self.flow_graph_keys

    def natural_list_at(self, path: tuple[Any, ...]) -> KeyedList | None:
        """The natural list the schema declares at ``path``, if any. A list item segment matches no key."""
        for list_path, keyed in self.natural_lists:
            if path == list_path:
                return keyed
        return None

    def listed_at(self, path: tuple[Any, ...]) -> KeyedList:
        """The keyed list whose items a checked path names at ``path``: a natural list, or else a table.

        Only a path that a write already checked may name list items, so the
        field's type is not read again.
        """
        return self.natural_list_at(path) or self.table

    def keyed_list_at(self, node: Any, path: tuple[Any, ...]) -> KeyedList | None:
        """Return the keyed list a node holds at ``path``, or None if the schema declares none there.

        A table is declared at every template field's ``value`` whose field
        matches one of the schema's ``when_field`` conditions.
        """

        def field_key(field_path: tuple[str, ...], key: str) -> Any:
            field = node
            for part in (*field_path, key):
                if not isinstance(field, dict) or part not in field:
                    return _MISSING
                field = field[part]
            return field

        return self.keyed_list_by(path, field_key)

    def field_value_list(self, name: str, field: Any) -> KeyedList | None:
        """The keyed list a template field's ``value`` is, given the field itself."""

        def field_key(_field_path: tuple[str, ...], key: str) -> Any:
            if not isinstance(field, dict) or key not in field:
                return _MISSING
            return field[key]

        return self.keyed_list_by(field_value_path(name), field_key)

    def keyed_list_by(
        self, path: tuple[Any, ...], field_key: Callable[[tuple[str, ...], str], Any]
    ) -> KeyedList | None:
        """The keyed list at ``path``, a path of object keys.

        When a table pattern matches, it reads the keys of the template field
        that ``when_field`` names through ``field_key(field_path, key)``, which
        returns ``_MISSING`` for a field that is not an object or lacks the key.
        """
        for part in path:
            if part.__class__ is not str:
                return None
        keyed = self.natural_list_at(path)
        if keyed is not None:
            return keyed
        if len(path) != len(self.table_path):
            return None
        wildcard = None
        for index, (part, pattern) in enumerate(zip(path, self.table_path, strict=True)):
            if pattern == WILDCARD:
                wildcard = index
            elif part != pattern:
                return None
        if wildcard is None:
            return self.table
        field_path = path[: wildcard + 1]
        for condition in self.table_when_field:
            if all(_json_equal(field_key(field_path, key), value) for key, value in condition.items()):
                return self.table
        return None

    def is_table_at(self, node: Any, path: tuple[Any, ...]) -> bool:
        """Whether the list at ``path`` of ``node`` is a table."""
        keyed = self.keyed_list_at(node, path)
        return keyed is not None and keyed.kind == "table"


def _json_equal(left: Any, right: Any) -> bool:
    """Equal as two JSON values are: a bool is never a number."""
    if left is _MISSING:
        return False
    if isinstance(left, bool) or isinstance(right, bool):
        return left.__class__ is right.__class__ and left == right
    return left == right


def _paths(raw: list[list[str]]) -> tuple[SchemaPath, ...]:
    return tuple(tuple(path) for path in raw)


@lru_cache(maxsize=1)
def load_node_schema() -> NodeSchema:
    """Load and index ``node_schema.json``."""
    raw = json.loads(NODE_SCHEMA_PATH.read_text(encoding="utf-8"))
    view_state = raw["view_state"]
    keyed_lists = raw["keyed_lists"]
    tables = keyed_lists["tables"]
    return NodeSchema(
        version=raw["version"],
        flow_graph_keys=frozenset(view_state["flow"]["except"]),
        node_view_state=frozenset(view_state["node"]),
        node_view_state_paths=_paths(view_state["node_paths"]),
        template_view_state=frozenset(view_state["template"]),
        field_view_state=frozenset(view_state["template_field"]),
        edge_view_state=frozenset(view_state["edge"]),
        value_unit=tuple(raw["field_units"]["value"]),
        toggles=tuple(raw["field_units"]["toggles"]),
        recursed_paths=frozenset(_paths(raw["whole_values"]["recursed"])),
        natural_lists=tuple(
            (tuple(entry["path"]), KeyedList(kind="natural", key=tuple(entry["key"]), position=entry["position"]))
            for entry in keyed_lists["natural"]
        ),
        table_path=tuple(tables["path"]),
        table_when_field=tuple(tables["when_field"]),
        table=KeyedList(kind="table", key=(tables["id"],), position=tables["position"]),
    )


NODE_SCHEMA = load_node_schema()

# The value a field key reader returns for a key that is not there.
MISSING = _MISSING
