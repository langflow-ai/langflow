"""The server's own account of what changed, and what it must never write down."""

from langflow.services.flow_audit.diff import diff_graphs, render_value


def node(node_id: str, display_name: str, fields: dict | None = None, position=(0, 0)) -> dict:
    return {
        "id": node_id,
        "position": {"x": position[0], "y": position[1]},
        "data": {
            "id": node_id,
            "node": {
                "display_name": display_name,
                "template": {name: {"display_name": name, **spec} for name, spec in (fields or {}).items()},
            },
        },
    }


def graph(nodes: list[dict], edges: list[dict] | None = None) -> dict:
    return {"nodes": nodes, "edges": edges or [], "viewport": {"x": 0, "y": 0, "zoom": 1}}


def test_a_short_field_change_carries_both_values():
    base = graph([node("a", "Chat Input", {"input_value": {"value": "this is a test"}})])
    after = graph([node("a", "Chat Input", {"input_value": {"value": "this is a test 2"}})])

    [group] = diff_graphs(base, after)

    assert group["label"] == "Chat Input"
    assert group["changes"] == [
        {
            "kind": "field",
            "field": "input_value",
            "label": "input_value",
            "before": "this is a test",
            "after": "this is a test 2",
        }
    ]


def test_a_secret_is_recorded_as_touched_and_never_as_a_value():
    """A value written here is a value on disk for as long as the row is kept."""
    base = graph([node("a", "OpenAI", {"api_key": {"value": "sk-live-old", "password": True}})])
    after = graph([node("a", "OpenAI", {"api_key": {"value": "sk-live-new", "password": True}})])

    [group] = diff_graphs(base, after)
    [change] = group["changes"]

    assert change["secret"] is True
    assert "sk-live-old" not in str(group)
    assert "sk-live-new" not in str(group)
    assert "before" not in change
    assert "after" not in change


def test_a_secretstr_typed_field_is_treated_as_a_secret():
    base = graph([node("a", "OpenAI", {"token": {"value": "one", "type": "SecretStr"}})])
    after = graph([node("a", "OpenAI", {"token": {"value": "two", "type": "SecretStr"}})])

    [group] = diff_graphs(base, after)

    assert group["changes"][0]["secret"] is True
    assert "two" not in str(group)


def test_a_long_value_is_truncated_rather_than_stored_whole():
    """Otherwise the trail grows with the content of the flow, which is what makes it expensive."""
    base = graph([node("a", "Prompt", {"template": {"value": "x" * 4000}})])
    after = graph([node("a", "Prompt", {"template": {"value": "y" * 4000}})])

    [group] = diff_graphs(base, after)
    [change] = group["changes"]

    assert change["truncated"] is True
    assert len(change["before"]) <= 60
    assert len(change["after"]) <= 60


def test_moving_a_node_is_a_change_of_its_own():
    base = graph([node("a", "Chat Input", position=(0, 0))])
    after = graph([node("a", "Chat Input", position=(220, 140))])

    [group] = diff_graphs(base, after)

    assert group["changes"] == [{"kind": "moved"}]


def test_every_change_to_one_component_lands_in_one_group():
    base = graph([node("a", "Chat Input", {"input_value": {"value": "one"}}, position=(0, 0))])
    after = graph([node("a", "Chat Input", {"input_value": {"value": "two"}}, position=(90, 90))])

    groups = diff_graphs(base, after)

    assert len(groups) == 1
    assert len(groups[0]["changes"]) == 2


def test_added_and_removed_components_are_reported():
    base = graph([node("a", "Chat Input")])
    after = graph([node("b", "Chat Output")])

    badges = {group["label"]: group["badge"] for group in diff_graphs(base, after)}

    assert badges == {"Chat Input": "removed", "Chat Output": "added"}


def test_edges_are_reported_by_the_components_they_join():
    base = graph([node("a", "Chat Input"), node("b", "Chat Output")])
    after = graph(
        [node("a", "Chat Input"), node("b", "Chat Output")],
        [{"id": "e1", "source": "a", "target": "b"}],
    )

    [group] = diff_graphs(base, after)

    assert group["label"] == "Chat Input → Chat Output"
    assert group["badge"] == "added"


def test_an_identical_graph_produces_nothing():
    same = graph([node("a", "Chat Input", {"input_value": {"value": "one"}})])

    assert diff_graphs(same, same) == []


def test_key_order_alone_is_not_a_change():
    base = graph([node("a", "Agent", {"config": {"value": {"b": 2, "a": 1}}})])
    after = graph([node("a", "Agent", {"config": {"value": {"a": 1, "b": 2}}})])

    assert diff_graphs(base, after) == []


def test_render_value_survives_something_it_cannot_serialise():
    assert render_value(object()) != ""


def test_template_metadata_is_not_treated_as_a_field():
    """A real template carries `_type` as a bare string beside its fields."""
    base = graph([node("a", "Chat Input", {"input_value": {"value": "one"}})])
    after = graph([node("a", "Chat Input", {"input_value": {"value": "two"}})])
    for g in (base, after):
        g["nodes"][0]["data"]["node"]["template"]["_type"] = "Component"

    [group] = diff_graphs(base, after)

    assert [c["field"] for c in group["changes"]] == ["input_value"]


def test_a_node_whose_template_is_not_a_mapping_is_survivable():
    base = graph([node("a", "Chat Input")])
    base["nodes"][0]["data"]["node"]["template"] = "not a template"
    after = graph([node("a", "Chat Input", {"f": {"value": "x"}})])

    assert diff_graphs(base, after)[0]["badge"] == "modified"


def test_a_model_selection_reads_as_its_name():
    """Serialised whole, one model change filled the dialog with twenty lines of JSON."""
    picked = [
        {
            "name": "claude-fable-5-1",
            "provider": "Anthropic",
            "icon": "Anthropic",
            "metadata": {"context_length": 128000},
        }
    ]
    base = graph([node("a", "Agent", {"model": {"value": picked}})])
    after = graph([node("a", "Agent", {"model": {"value": []}})])

    [group] = diff_graphs(base, after)
    [change] = group["changes"]

    assert change["before"] == "claude-fable-5-1"
    assert change["after"] == "[]"
    assert "metadata" not in str(change)


def test_a_list_without_names_is_still_serialised():
    base = graph([node("a", "Agent", {"tools": {"value": [{"kind": "search"}]}})])
    after = graph([node("a", "Agent", {"tools": {"value": [{"kind": "browse"}]}})])

    [group] = diff_graphs(base, after)

    assert "browse" in group["changes"][0]["after"]


def test_frontend_metadata_never_appears_as_a_change():
    """`_frontend_node_flow_id` is template metadata, not something a person edited."""
    base = graph([node("a", "Agent", {"_frontend_node_flow_id": {"value": "flow-1"}, "f": {"value": "one"}})])
    after = graph([node("a", "Agent", {"_frontend_node_flow_id": {"value": "flow-2"}, "f": {"value": "one"}})])

    assert diff_graphs(base, after) == []


def test_an_absent_value_reads_as_a_dash_not_a_hole():
    """Otherwise the sentence renders as "updated from  to claude-fable-5-1"."""
    base = graph([node("a", "Agent", {"model": {"value": None}})])
    after = graph([node("a", "Agent", {"model": {"value": [{"name": "claude-fable-5-1"}]}})])

    [group] = diff_graphs(base, after)
    [change] = group["changes"]

    assert change["before"] == "—"
    assert change["after"] == "claude-fable-5-1"
