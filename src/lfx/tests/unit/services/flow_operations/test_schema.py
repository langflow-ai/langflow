"""The node schema file and the keyed lists it declares."""

from __future__ import annotations

import json

import pytest
from lfx.services.flow_operations import KeyedList, load_node_schema
from lfx.services.flow_operations.schema import NODE_SCHEMA_PATH


def _node(template: dict) -> dict:
    return {"id": "n", "data": {"node": {"template": template, "outputs": []}}}


def test_schema_file_is_versioned_json():
    raw = json.loads(NODE_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert raw["version"] == 1
    assert load_node_schema().version == 1


def test_view_state_matches_the_protocol():
    schema = load_node_schema()

    assert schema.flow_view_state == {"viewport"}
    assert schema.node_view_state == {"selected", "dragging", "resizing", "measured", "width", "height"}
    assert schema.node_view_state_paths == (("data", "node", "last_updated"), ("data", "node", "lf_version"))
    assert schema.edge_view_state == {"selected", "animated", "className"}
    assert "options" in schema.field_view_state
    assert "value" not in schema.field_view_state
    assert schema.value_unit == ("value", "load_from_db", "file_path", "_connection_mode")
    assert schema.toggles == ("advanced", "tool_mode")


def test_field_units_and_view_state_do_not_overlap():
    schema = load_node_schema()
    units = set(schema.value_unit) | set(schema.toggles)

    assert not units & schema.field_view_state
    assert len(units) == len(schema.value_unit) + len(schema.toggles)


@pytest.mark.parametrize(
    ("field", "expected_kind"),
    [
        ({"type": "table", "value": []}, "table"),
        ({"_input_type": "TableInput", "value": []}, "table"),
        ({"type": "str", "value": []}, None),
    ],
)
def test_table_values_are_keyed_by_field_type(field, expected_kind):
    keyed = load_node_schema().keyed_list_at(_node({"f": field}), ("data", "node", "template", "f", "value"))

    assert (keyed.kind if keyed else None) == expected_kind


def test_natural_key_lists():
    schema = load_node_schema()
    node = _node({"tools_metadata": {"type": "tools", "value": []}})

    outputs = schema.keyed_list_at(node, ("data", "node", "outputs"))
    tools = schema.keyed_list_at(node, ("data", "node", "template", "tools_metadata", "value"))

    assert outputs == KeyedList(kind="natural", key=("name",))
    assert tools == KeyedList(kind="natural", key=("tags", 0))
    assert tools.key_of({"name": "renamed", "tags": ["search"]}) == "search"
    assert tools.key_of({"name": "untagged", "tags": []}) is None
    assert schema.keyed_list_at(node, ("data", "node", "base_classes")) is None


def test_table_sort_orders_by_position_then_id():
    table = load_node_schema().table
    rows = [
        {"_id": "b", "_pos": "a1"},
        {"_id": "a", "_pos": "a1"},
        {"_id": "c", "_pos": "a0V"},
        {"_id": "d", "_pos": "Zz"},
    ]

    table.sort(rows)

    assert [row["_id"] for row in rows] == ["d", "c", "a", "b"]
