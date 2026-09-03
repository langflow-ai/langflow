"""Tests for the flow version diff engine.

The load-bearing tests here are the redaction ones. A diff runs server-side
precisely so a secret rotation can be reported as a change without the value
crossing the wire, so several tests assert on the serialized payload rather than
on the structure alone.
"""

from __future__ import annotations

import json

import pytest
from langflow.utils.flow_diff import (
    MAX_CODE_FIELD_CHARS,
    MAX_MODIFIED_NODE_DETAILS,
    MAX_VALUE_PREVIEW_CHARS,
    FlowDiffSide,
    FlowDiffStripError,
    compute_flow_diff,
)
from langflow.utils.flow_secrets import strip_secret_field_values


def _node(node_id: str = "n1", template: dict | None = None, display_name: str = "Node", **extra) -> dict:
    node = {
        "id": node_id,
        "type": "genericNode",
        "position": {"x": 0, "y": 0},
        "data": {
            "id": node_id,
            "type": "Component",
            "node": {"display_name": display_name, "template": template if template is not None else {}},
        },
    }
    node.update(extra)
    return node


def _flow(nodes: list | None = None, edges: list | None = None) -> dict:
    return {"nodes": nodes if nodes is not None else [], "edges": edges if edges is not None else []}


def _side(data: dict | None) -> FlowDiffSide:
    """Pair a payload with its scrubbed counterpart, exactly as the route does."""
    return FlowDiffSide(raw=data, stripped=strip_secret_field_values(data) if data is not None else None)


def _diff(before: dict | None, after: dict | None) -> dict:
    return compute_flow_diff(_side(before), _side(after))


def _only_modified(diff: dict) -> dict:
    assert len(diff["nodes"]["modified"]) == 1
    return diff["nodes"]["modified"][0]


def _field(template_value, name: str = "temperature", **extra) -> dict:
    field = {"name": name, "type": "float", "value": template_value}
    field.update(extra)
    return {"_type": "Component", name: field}


def test_identical_payloads_report_no_changes() -> None:
    flow = _flow([_node(template=_field(0.7))])

    diff = _diff(flow, flow)

    assert diff["identical"] is True
    assert diff["summary"]["nodes_unchanged"] == 1
    assert diff["nodes"]["modified"] == []


def test_added_node_is_reported_with_a_bounded_reference() -> None:
    after = _flow([_node("n1", _field(0.7)), _node("n2", _field(0.1), display_name="Second")])

    diff = _diff(_flow([_node("n1", _field(0.7))]), after)

    assert diff["summary"]["nodes_added"] == 1
    added = diff["nodes"]["added"][0]
    assert added == {
        "id": "n2",
        "display_name": "Second",
        "component_type": "Component",
        "node_type": "genericNode",
    }


def test_removed_node_is_reported() -> None:
    before = _flow([_node("n1", _field(0.7)), _node("n2", _field(0.1))])

    diff = _diff(before, _flow([_node("n1", _field(0.7))]))

    assert diff["summary"]["nodes_removed"] == 1
    assert diff["nodes"]["removed"][0]["id"] == "n2"


def test_modified_field_reports_before_and_after() -> None:
    diff = _diff(_flow([_node(template=_field(0.7))]), _flow([_node(template=_field(0.2))]))

    change = _only_modified(diff)["field_changes"][0]
    assert change["status"] == "modified"
    assert change["redacted"] is False
    assert change["before"] == 0.7
    assert change["after"] == 0.2
    assert diff["summary"]["fields_changed"] == 1


def test_added_and_removed_fields_report_the_present_side_only() -> None:
    before = _flow([_node(template={"_type": "Component"})])
    after = _flow([_node(template=_field("hello", name="prompt"))])

    added = _only_modified(_diff(before, after))["field_changes"][0]
    assert added["status"] == "added"
    assert added["after"] == "hello"
    assert "before" not in added

    removed = _only_modified(_diff(after, before))["field_changes"][0]
    assert removed["status"] == "removed"
    assert removed["before"] == "hello"
    assert "after" not in removed


def test_moving_a_node_on_the_canvas_is_not_a_change() -> None:
    before = _flow([_node(template=_field(0.7))])
    after = _flow([_node(template=_field(0.7))])
    after["nodes"][0]["position"] = {"x": 900, "y": 400}
    after["nodes"][0]["selected"] = True
    after["nodes"][0]["dragging"] = False
    after["nodes"][0]["measured"] = {"width": 10, "height": 20}

    assert _diff(before, after)["identical"] is True


def test_display_name_change_is_reported_separately_from_fields() -> None:
    before = _flow([_node(template=_field(0.7), display_name="Old")])
    after = _flow([_node(template=_field(0.7), display_name="New")])

    change = _only_modified(_diff(before, after))
    assert change["display_name_change"] == {"before": "Old", "after": "New"}
    assert change["field_changes"] == []


def test_non_template_change_surfaces_as_a_dotted_path() -> None:
    before = _flow([_node(template=_field(0.7))])
    after = _flow([_node(template=_field(0.7))])
    after["nodes"][0]["data"]["node"]["outputs"] = [{"name": "out"}]

    change = _only_modified(_diff(before, after))
    assert "data.node.outputs" in change["other_changed_keys"]


def test_rotated_secret_is_reported_as_changed_without_disclosing_either_value() -> None:
    """The headline security property: one bit out, no values."""
    secret_field = {"_type": "Component", "api_key": {"name": "api_key", "password": True, "value": "sk-OLD-11111111"}}
    rotated = {"_type": "Component", "api_key": {"name": "api_key", "password": True, "value": "sk-NEW-22222222"}}

    diff = _diff(_flow([_node(template=secret_field)]), _flow([_node(template=rotated)]))

    change = _only_modified(diff)["field_changes"][0]
    assert change["status"] == "modified"
    assert change["redacted"] is True
    assert "before" not in change
    assert "after" not in change
    assert diff["summary"]["secrets_changed"] == 1

    serialized = json.dumps(diff)
    assert "sk-OLD-11111111" not in serialized
    assert "sk-NEW-22222222" not in serialized


def test_unchanged_secret_is_not_reported_at_all() -> None:
    template = {"_type": "Component", "api_key": {"name": "api_key", "password": True, "value": "sk-SAME-1234"}}
    flow = _flow([_node(template=template)])

    diff = _diff(flow, flow)

    assert diff["identical"] is True
    assert diff["summary"]["secrets_changed"] == 0


def test_rebinding_a_load_from_db_field_is_redacted() -> None:
    """The bound value is a variable name, but the scrubber nulls it, so it is withheld."""
    before = {"_type": "C", "api_key": {"name": "api_key", "password": True, "load_from_db": True, "value": "KEY_A"}}
    after = {"_type": "C", "api_key": {"name": "api_key", "password": True, "load_from_db": True, "value": "KEY_B"}}

    change = _only_modified(_diff(_flow([_node(template=before)]), _flow([_node(template=after)])))["field_changes"][0]

    assert change["redacted"] is True
    assert "before" not in change


def test_mcp_field_change_is_redacted() -> None:
    """The scrubber reshapes MCP values, so neither side can be shown verbatim."""
    before = {"_type": "C", "server": {"name": "server", "type": "mcp", "value": {"name": "a", "token": "t1"}}}
    after = {"_type": "C", "server": {"name": "server", "type": "mcp", "value": {"name": "b", "token": "t2"}}}

    diff = _diff(_flow([_node(template=before)]), _flow([_node(template=after)]))

    change = _only_modified(diff)["field_changes"][0]
    assert change["redacted"] is True
    assert "t1" not in json.dumps(diff)
    assert "t2" not in json.dumps(diff)


def test_secret_named_field_is_redacted_even_without_the_password_flag() -> None:
    before = {"_type": "C", "connection_string": {"name": "connection_string", "value": "postgres://u:p1@h/db"}}
    after = {"_type": "C", "connection_string": {"name": "connection_string", "value": "postgres://u:p2@h/db"}}

    diff = _diff(_flow([_node(template=before)]), _flow([_node(template=after)]))

    assert _only_modified(diff)["field_changes"][0]["redacted"] is True
    assert "p1" not in json.dumps(diff)


def test_code_change_reports_line_counts_and_a_unified_diff() -> None:
    before = {"_type": "C", "code": {"name": "code", "type": "code", "value": "def f():\n    return 1\n"}}
    after = {"_type": "C", "code": {"name": "code", "type": "code", "value": "def f():\n    return 2\n\nx = 3\n"}}

    diff = _diff(_flow([_node(template=before)]), _flow([_node(template=after)]))

    change = _only_modified(diff)
    assert change["field_changes"] == []
    code_change = change["code_changes"][0]
    assert code_change["field_name"] == "code"
    assert code_change["added_lines"] == 3
    assert code_change["removed_lines"] == 1
    assert "return 2" in code_change["unified_diff"]
    assert diff["summary"]["code_fields_changed"] == 1


def test_code_diff_omits_the_empty_file_headers() -> None:
    """A template field has no filename, so ``---``/``+++`` would render as blank rows."""
    before = {"_type": "C", "code": {"name": "code", "type": "code", "value": "a = 1\n"}}
    after = {"_type": "C", "code": {"name": "code", "type": "code", "value": "a = 2\n"}}

    diff = _diff(_flow([_node(template=before)]), _flow([_node(template=after)]))

    unified = _only_modified(diff)["code_changes"][0]["unified_diff"]
    lines = unified.split("\n")
    assert not any(line.startswith(("---", "+++")) for line in lines)
    assert lines[0].startswith("@@")
    # Counts are taken before the headers are dropped, so they stay correct.
    assert _only_modified(diff)["code_changes"][0]["added_lines"] == 1
    assert _only_modified(diff)["code_changes"][0]["removed_lines"] == 1


def test_oversized_code_field_reports_the_change_without_a_diff() -> None:
    big = "x = 1\n" * (MAX_CODE_FIELD_CHARS // 4)
    before = {"_type": "C", "code": {"name": "code", "type": "code", "value": big}}
    after = {"_type": "C", "code": {"name": "code", "type": "code", "value": big + "y = 2\n"}}

    code_change = _only_modified(_diff(_flow([_node(template=before)]), _flow([_node(template=after)])))[
        "code_changes"
    ][0]

    assert code_change["truncated"] is True
    assert code_change["unified_diff"] is None


def test_long_value_is_truncated_and_flagged() -> None:
    long_value = "a" * (MAX_VALUE_PREVIEW_CHARS + 100)
    before = _flow([_node(template=_field("short", name="prompt"))])
    after = _flow([_node(template=_field(long_value, name="prompt"))])

    change = _only_modified(_diff(before, after))["field_changes"][0]

    assert change["after_truncated"] is True
    assert len(change["after"]) == MAX_VALUE_PREVIEW_CHARS


def test_a_side_whose_scrubbing_failed_closed_is_refused() -> None:
    """strip_version_data returns None on failure; diffing raw instead would leak."""
    side = FlowDiffSide(raw=_flow([_node()]), stripped=None)

    with pytest.raises(FlowDiffStripError):
        compute_flow_diff(side, _side(_flow()))


def test_missing_data_on_one_side_reports_everything_as_added() -> None:
    diff = _diff(None, _flow([_node("n1"), _node("n2")]))

    assert diff["summary"]["nodes_added"] == 2
    assert diff["summary"]["nodes_removed"] == 0
    assert diff["identical"] is False


@pytest.mark.parametrize(
    "malformed",
    [
        {"nodes": "not-a-list", "edges": []},
        {"nodes": [None, "text", 42], "edges": []},
        {"nodes": [{"no_id": True}], "edges": []},
        {"nodes": [{"id": "n1"}], "edges": "not-a-list"},
        {},
    ],
)
def test_malformed_payloads_do_not_raise(malformed: dict) -> None:
    diff = _diff(malformed, _flow([_node()]))

    assert isinstance(diff["summary"]["nodes_added"], int)


def test_non_dict_template_entries_are_skipped() -> None:
    """Nodes carry bare strings such as ``_type`` and ``backgroundColor`` in the template."""
    before = _flow([_node(template={"_type": "Component", "backgroundColor": "red"})])
    after = _flow([_node(template={"_type": "Component", "backgroundColor": "blue"})])

    diff = _diff(before, after)

    assert diff["nodes"]["modified"] == []
    assert diff["identical"] is True


def test_duplicate_node_ids_keep_the_first_occurrence() -> None:
    before = _flow([_node("n1", _field(0.7)), _node("n1", _field(0.9))])

    diff = _diff(before, _flow([_node("n1", _field(0.7))]))

    assert diff["identical"] is True


def test_edges_are_keyed_by_id() -> None:
    edge = {"id": "e1", "source": "n1", "target": "n2"}
    other = {"id": "e2", "source": "n2", "target": "n3"}

    diff = _diff(_flow(edges=[edge]), _flow(edges=[edge, other]))

    assert diff["summary"]["edges_added"] == 1
    assert diff["summary"]["edges_unchanged"] == 1
    assert diff["edges"]["added"][0]["id"] == "e2"


def test_edges_without_an_id_fall_back_to_a_composite_key() -> None:
    edge = {"source": "n1", "sourceHandle": "out", "target": "n2", "targetHandle": "in"}
    rewired = {"source": "n1", "sourceHandle": "out", "target": "n3", "targetHandle": "in"}

    diff = _diff(_flow(edges=[edge]), _flow(edges=[rewired]))

    assert diff["summary"]["edges_added"] == 1
    assert diff["summary"]["edges_removed"] == 1


def test_edge_handle_names_are_read_from_edge_data() -> None:
    edge = {
        "id": "e1",
        "source": "n1",
        "target": "n2",
        "data": {"sourceHandle": {"name": "text_output"}, "targetHandle": {"fieldName": "input_value"}},
    }

    added = _diff(_flow(), _flow(edges=[edge]))["edges"]["added"][0]

    assert added["source_handle_name"] == "text_output"
    assert added["target_handle_name"] == "input_value"


def test_node_detail_is_capped_while_summary_counts_stay_exact() -> None:
    total = MAX_MODIFIED_NODE_DETAILS + 5
    before = _flow([_node(f"n{index}", _field(0.1)) for index in range(total)])
    after = _flow([_node(f"n{index}", _field(0.2)) for index in range(total)])

    diff = _diff(before, after)

    assert diff["truncated"] is True
    assert diff["summary"]["nodes_modified"] == total
    assert len(diff["nodes"]["modified"]) == MAX_MODIFIED_NODE_DETAILS
