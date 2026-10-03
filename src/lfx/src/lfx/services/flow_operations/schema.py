"""The node schema: where the units, view state and keyed lists of a flow are.

``node_schema.json`` is the single description both engines read (the editor
keeps a byte-identical copy), so neither hard-codes paths. This module loads it
once and answers the questions the engine asks while walking a path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from lfx.services.flow_operations.canonical import utf16_sort_key

NODE_SCHEMA_PATH = Path(__file__).with_name("node_schema.json")
WILDCARD = "*"

SchemaPath = tuple[str, ...]
KeyPath = tuple[str | int, ...]


@dataclass(frozen=True)
class KeyedList:
    """A list whose items are addressed by a key instead of an index.

    ``natural`` lists (outputs, tool actions) are selected with
    ``{"key": ...}`` and keep the order writes leave them in. ``table`` lists
    are selected with ``{"id": ...}`` and kept sorted by ``(position, id)``.
    """

    kind: Literal["natural", "table"]
    key: KeyPath
    position: str | None = None

    @property
    def selector_name(self) -> str:
        return "id" if self.kind == "table" else "key"

    def key_of(self, item: Any) -> str | None:
        """Return an item's key, or None when the item has none."""
        value: Any = item
        for part in self.key:
            if isinstance(part, str) and isinstance(value, dict):
                value = value.get(part)
            elif isinstance(part, int) and isinstance(value, list) and 0 <= part < len(value):
                value = value[part]
            else:
                return None
        return value if isinstance(value, str) else None

    def find(self, items: list[Any], key: str) -> int | None:
        """Return the index of the first item with ``key``, or None."""
        for index, item in enumerate(items):
            if self.key_of(item) == key:
                return index
        return None

    def sort(self, items: list[Any]) -> None:
        """Sort table rows in place by ``(position, id)``, comparing UTF-16 code units."""
        if self.kind != "table" or self.position is None:
            return

        def order(item: Any) -> tuple[bytes, bytes]:
            position = item.get(self.position) if isinstance(item, dict) else None
            row_id = self.key_of(item)
            return (
                utf16_sort_key(position) if isinstance(position, str) else b"",
                utf16_sort_key(row_id) if row_id is not None else b"",
            )

        items.sort(key=order)


@dataclass(frozen=True)
class NodeSchema:
    version: int
    flow_view_state: frozenset[str]
    node_view_state: frozenset[str]
    node_view_state_paths: tuple[SchemaPath, ...]
    template_view_state: frozenset[str]
    field_view_state: frozenset[str]
    edge_view_state: frozenset[str]
    value_unit: tuple[str, ...]
    toggles: tuple[str, ...]
    whole_value_paths: tuple[SchemaPath, ...]
    recursed_paths: tuple[SchemaPath, ...]
    natural_lists: tuple[tuple[SchemaPath, KeyedList], ...]
    table_path: SchemaPath
    table_when_field: tuple[dict[str, Any], ...]
    table: KeyedList

    def keyed_list_at(self, node: dict[str, Any], path: tuple[Any, ...]) -> KeyedList | None:
        """Return the keyed list a node holds at ``path``, or None if the schema declares none there."""
        if not all(isinstance(part, str) for part in path):
            return None
        for list_path, keyed in self.natural_lists:
            if path == list_path:
                return keyed
        if len(path) != len(self.table_path):
            return None
        wildcard_index = None
        for index, (part, pattern) in enumerate(zip(path, self.table_path, strict=True)):
            if pattern == WILDCARD:
                wildcard_index = index
            elif part != pattern:
                return None
        if wildcard_index is None:
            return self.table
        field = _read(node, path[: wildcard_index + 1])
        if isinstance(field, dict) and any(
            all(field.get(key) == value for key, value in condition.items()) for condition in self.table_when_field
        ):
            return self.table
        return None


def _read(value: Any, path: tuple[str, ...]) -> Any:
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


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
        flow_view_state=frozenset(view_state["flow"]),
        node_view_state=frozenset(view_state["node"]),
        node_view_state_paths=_paths(view_state["node_paths"]),
        template_view_state=frozenset(view_state["template"]),
        field_view_state=frozenset(view_state["template_field"]),
        edge_view_state=frozenset(view_state["edge"]),
        value_unit=tuple(raw["field_units"]["value"]),
        toggles=tuple(raw["field_units"]["toggles"]),
        whole_value_paths=_paths(raw["whole_values"]["paths"]),
        recursed_paths=_paths(raw["whole_values"]["recursed"]),
        natural_lists=tuple(
            (tuple(entry["path"]), KeyedList(kind="natural", key=tuple(entry["key"])))
            for entry in keyed_lists["natural"]
        ),
        table_path=tuple(tables["path"]),
        table_when_field=tuple(tables["when_field"]),
        table=KeyedList(kind="table", key=(tables["id"],), position=tables["position"]),
    )
