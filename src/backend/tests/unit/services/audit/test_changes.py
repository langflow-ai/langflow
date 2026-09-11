"""What an edit touched, named — and never what it became."""

from langflow.services.audit.changes import CHANGES_LIMIT, summarize_flow_changes

SECRET = "sk-do-not-store-me"  # noqa: S105  # pragma: allowlist secret


def _node(node_id: str, label: str, template: dict | None = None) -> dict:
    return {
        "id": node_id,
        "position": {"x": 0, "y": 0},
        "data": {"node": {"display_name": label, "template": template or {}}},
    }


def _graph(*nodes: dict, edges: list | None = None) -> dict:
    return {"nodes": list(nodes), "edges": edges or [], "viewport": {"x": 0, "y": 0, "zoom": 1}}


def test_a_changed_field_is_named_by_component_and_field():
    before = _graph(_node("a", "Agent", {"model_name": {"value": "gpt-4"}}))
    after = _graph(_node("a", "Agent", {"model_name": {"value": "gpt-5"}}))

    names, total = summarize_flow_changes(before, after)

    assert names == ["Agent.model_name"]
    assert total == 1


def test_a_secret_value_never_appears_in_the_summary():
    before = _graph(_node("a", "Agent", {"api_key": {"value": "", "password": True}}))
    after = _graph(_node("a", "Agent", {"api_key": {"value": SECRET, "password": True}}))

    names, _ = summarize_flow_changes(before, after)

    assert names == ["Agent.api_key"]
    assert SECRET not in str(names)


def test_added_and_removed_components_are_signed():
    before = _graph(_node("a", "Prompt"))
    after = _graph(_node("b", "Chat Output"))

    names, _ = summarize_flow_changes(before, after)

    assert sorted(names) == ["+Chat Output", "-Prompt"]


def test_connections_are_counted_not_enumerated():
    before = _graph(_node("a", "Agent"), edges=[])
    after = _graph(_node("a", "Agent"), edges=[{"id": "e1"}, {"id": "e2"}])

    names, _ = summarize_flow_changes(before, after)

    assert names == ["+2 connections"]


def test_a_no_op_save_names_nothing():
    graph = _graph(_node("a", "Agent", {"model_name": {"value": "gpt-5"}}))

    assert summarize_flow_changes(graph, graph) == ([], 0)


def test_moving_a_component_is_not_a_change():
    before = _graph(_node("a", "Agent"))
    after = _graph({**_node("a", "Agent"), "position": {"x": 900, "y": 400}})

    assert summarize_flow_changes(before, after) == ([], 0)


def test_template_metadata_is_not_mistaken_for_a_field():
    """A real template carries ``_type``, a bare string, beside its fields."""
    before = _graph(_node("a", "Agent", {"_type": "Component", "model_name": {"value": "x"}}))
    after = _graph(_node("a", "Agent", {"_type": "Component", "model_name": {"value": "y"}}))

    names, _ = summarize_flow_changes(before, after)

    assert names == ["Agent.model_name"]


def test_a_mass_edit_is_capped_but_counted_honestly():
    fields = {f"field_{i}": {"value": i} for i in range(CHANGES_LIMIT * 2)}
    before = _graph(_node("a", "Agent", fields))
    after = _graph(_node("a", "Agent", {name: {"value": "changed"} for name in fields}))

    names, total = summarize_flow_changes(before, after)

    assert len(names) == CHANGES_LIMIT
    assert total == CHANGES_LIMIT * 2
