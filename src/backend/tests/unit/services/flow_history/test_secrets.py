"""Recorded operations and reconstructed graphs never leave the server with literal secrets."""

from __future__ import annotations

import copy

from langflow.services.flow_history.secrets import strip_graph_secrets, strip_operation_secrets
from lfx.services.flow_operations import derive_flow_operations, dump_flow_operation

KNOWN_VARIABLES = frozenset({"OPENAI_API_KEY"})


def _node(node_id: str, **template) -> dict:
    return {"id": node_id, "data": {"type": "OpenAI", "node": {"display_name": "OpenAI", "template": template}}}


def _secret_field(value, *, load_from_db: bool = False) -> dict:
    return {"name": "api_key", "type": "str", "password": True, "load_from_db": load_from_db, "value": value}


def _operations(base: dict, target: dict) -> list[dict]:
    return [dump_flow_operation(operation) for operation in derive_flow_operations(base, target).operations]


def _graph(*nodes) -> dict:
    return {"nodes": list(nodes), "edges": []}


def _value_entry(update: dict) -> dict:
    """Return the write of a field's ``value``; the diff writes the field's whole value unit."""
    return next(entry for entry in update["updates"] if entry["path"][-1] == "value")


def _value_index(update: dict) -> int:
    return update["updates"].index(_value_entry(update))


def test_added_nodes_lose_literal_secrets_and_keep_variable_names():
    target = _graph(
        _node("a", api_key=_secret_field("sk-literal-secret")),
        _node("b", api_key=_secret_field("OPENAI_API_KEY", load_from_db=True)),
    )
    (add_nodes,) = _operations(_graph(), target)

    stripped = strip_operation_secrets(add_nodes, KNOWN_VARIABLES)

    fields = [node["data"]["node"]["template"]["api_key"]["value"] for node in stripped["nodes"]]
    assert fields == [None, "OPENAI_API_KEY"]
    # The recorded operation itself is untouched; only the copy that leaves is stripped.
    assert add_nodes["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] == "sk-literal-secret"


def test_a_set_field_on_a_secret_value_is_stripped_using_its_recorded_metadata():
    base = _graph(_node("a", api_key=_secret_field("old")))
    target = copy.deepcopy(base)
    target["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] = "sk-new-secret"
    (update,) = _operations(base, target)
    assert _value_entry(update)["template_field"]["password"] is True

    stripped = strip_operation_secrets(update, KNOWN_VARIABLES)

    assert stripped["updates"][_value_index(update)]["value"] is None


def test_a_set_field_naming_a_known_variable_keeps_the_name():
    base = _graph(_node("a", api_key=_secret_field("OLD_KEY", load_from_db=True)))
    target = copy.deepcopy(base)
    target["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] = "OPENAI_API_KEY"
    (update,) = _operations(base, target)

    index = _value_index(update)
    assert strip_operation_secrets(update, KNOWN_VARIABLES)["updates"][index]["value"] == "OPENAI_API_KEY"
    # A name that is not one of the owner's variables could be a literal secret.
    assert strip_operation_secrets(update, frozenset())["updates"][index]["value"] is None


def test_a_whole_secret_field_set_at_once_is_stripped():
    base = _graph(_node("a"))
    target = _graph(_node("a", api_key=_secret_field("sk-literal-secret")))
    (update,) = _operations(base, target)

    stripped = strip_operation_secrets(update, KNOWN_VARIABLES)

    assert stripped["updates"][0]["value"]["value"] is None
    assert stripped["updates"][0]["value"]["password"] is True


def test_a_structured_secret_value_is_written_and_stripped_whole():
    base = _graph(_node("a", api_key=_secret_field({"header": "Bearer old"})))
    target = copy.deepcopy(base)
    target["nodes"][0]["data"]["node"]["template"]["api_key"]["value"]["header"] = "Bearer sk-new"
    (update,) = _operations(base, target)
    assert _value_entry(update)["path"] == ["data", "node", "template", "api_key", "value"]

    assert strip_operation_secrets(update, KNOWN_VARIABLES)["updates"][_value_index(update)]["value"] is None


def test_a_write_inside_a_secret_value_is_removed():
    update = {
        "type": "update_nodes",
        "updates": [
            {
                "id": "a",
                "op": "set_field",
                "path": ["data", "node", "template", "api_key", "value", "header"],
                "value": "Bearer sk-new",
                "template_field": {"name": "api_key", "type": "str", "password": True},
            }
        ],
    }

    assert strip_operation_secrets(update, KNOWN_VARIABLES)["updates"][0]["value"] is None


def test_table_cells_addressed_by_row_id_are_stripped():
    base = _graph(
        _node(
            "a",
            headers={
                "name": "headers",
                "type": "table",
                "table_schema": [{"name": "key"}, {"name": "value"}],
                "value": [{"_id": "r1", "_pos": "a0", "key": "Authorization", "value": "Bearer old"}],
            },
        )
    )
    target = copy.deepcopy(base)
    row = target["nodes"][0]["data"]["node"]["template"]["headers"]["value"][0]
    row["value"] = "Bearer sk-new"
    row["key"] = "X-Authorization"
    (update,) = _operations(base, target)
    assert [entry["path"][-2:] for entry in update["updates"]] == [[{"id": "r1"}, "key"], [{"id": "r1"}, "value"]]

    stripped = strip_operation_secrets(update, KNOWN_VARIABLES)

    # The key cell passes; the value cell is withheld because its row's key decides whether it is a secret.
    assert [entry["value"] for entry in stripped["updates"]] == ["X-Authorization", None]
    assert stripped["updates"][1]["path"] == update["updates"][1]["path"]


def test_a_whole_table_row_is_stripped_like_a_stored_row():
    update = {
        "type": "update_nodes",
        "updates": [
            {
                "id": "a",
                "op": "set_field",
                "path": ["data", "node", "template", "headers", "value", {"id": "r2"}],
                "value": {"_id": "r2", "_pos": "a1", "key": "Authorization", "value": "Bearer sk-new"},
                "template_field": {"name": "headers", "type": "table"},
            }
        ],
    }

    stripped = strip_operation_secrets(update, KNOWN_VARIABLES)["updates"][0]["value"]

    assert stripped == {"_id": "r2", "_pos": "a1", "key": "Authorization", "value": None}


def test_ordinary_values_pass_through():
    base = _graph(_node("a", text={"name": "text", "type": "str", "value": "hello"}))
    target = copy.deepcopy(base)
    target["nodes"][0]["data"]["node"]["template"]["text"]["value"] = "world"
    target["nodes"][0]["position"] = {"x": 3, "y": 4}
    (update,) = _operations(base, target)

    stripped = strip_operation_secrets(update, KNOWN_VARIABLES)

    assert [entry["value"] for entry in stripped["updates"]] == ["world", {"x": 3, "y": 4}]


def test_metadata_values_named_like_secrets_are_stripped():
    operation = {
        "type": "update_metadata",
        "fields": {"notes": "fine", "api_key": "sk-literal-secret"},  # pragma: allowlist secret
    }

    assert strip_operation_secrets(operation, KNOWN_VARIABLES)["fields"] == {"notes": "fine", "api_key": None}


def test_reconstructed_graphs_are_stripped_without_touching_the_original():
    graph = _graph(_node("a", api_key=_secret_field("sk-literal-secret")))

    stripped = strip_graph_secrets(graph, KNOWN_VARIABLES)

    assert stripped["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] is None
    assert graph["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] == "sk-literal-secret"
