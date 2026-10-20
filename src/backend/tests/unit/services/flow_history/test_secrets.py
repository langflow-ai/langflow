"""Recorded operations and reconstructed graphs never leave the server with literal secrets.

When the history records a batch, each write keeps the parts of its value
that the secret scrubbing changes in the graph after the batch. A read strips
by them. These tests record writes into real components and read them back.
"""

from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path

import langflow.initial_setup
import pytest
from langflow.services.flow_history.secrets import (
    SecretFinder,
    SecretPart,
    strip_graph_secrets,
    strip_operation_secrets,
)
from lfx.components.input_output import ChatInput
from lfx.components.models_and_agents.language_model import LanguageModelComponent
from lfx.components.models_and_agents.mcp_component import MCPToolsComponent
from lfx.services.flow_operations import derive_flow_operations, parse_flow_operation
from lfx_docling.components.docling.docling_remote import DoclingRemoteComponent

KNOWN_VARIABLES = frozenset({"OPENAI_API_KEY", "DOCLING_TOKEN"})
STARTER_PROJECTS = Path(langflow.initial_setup.__file__).parent / "starter_projects"
AWS_KEY = "AKIAIOSFODNN7EXAMPLE"  # pragma: allowlist secret - AWS's documented example key
BEARER = "Bearer sk-docling-literal-0123456789"  # pragma: allowlist secret
TEMPLATE = ["data", "node", "template"]


def _component_node(component, node_id: str) -> dict:
    node = component.to_frontend_node()
    node["id"] = node_id
    node["data"]["id"] = node_id
    node["position"] = {"x": 0, "y": 0}
    return node


def _graph(*nodes) -> dict:
    return {"nodes": list(nodes), "edges": []}


def _template(graph: dict, node_id: str = "a") -> dict:
    return next(node for node in graph["nodes"] if node["id"] == node_id)["data"]["node"]["template"]


def _record(base: dict, target: dict, known: frozenset[str] = KNOWN_VARIABLES) -> list[tuple]:
    """Record the change from ``base`` to ``target`` as the history does: each operation with its secret parts."""
    finder = SecretFinder(target, known)
    return [(operation, finder.secrets_of(operation)) for operation in derive_flow_operations(base, target).operations]


def _write(recorded: list[tuple], path: list) -> tuple:
    """Return the ``update_nodes`` that writes ``path``, its secret parts, and the index of that write."""
    for operation, secrets in recorded:
        for index, update in enumerate(getattr(operation, "updates", [])):
            if update.model_dump(mode="json")["path"] == path:
                return operation, secrets, index
    msg = f"no write at {path!r}"
    raise AssertionError(msg)


def _parts(secrets: tuple, index: int) -> list[dict]:
    return [part.to_json() for part in secrets[index]]


def _read(operation, secrets, index: int, known: frozenset[str] = KNOWN_VARIABLES) -> dict:
    return strip_operation_secrets(operation, secrets, known)["updates"][index]


# --- Docling Serve: a table whose value column loads global variables ---------------------

HEADERS_ROW = [*TEMPLATE, "api_headers", "value", {"key": "r2"}]


def _docling() -> dict:
    return _graph(_component_node(DoclingRemoteComponent(), "a"))


def _with_header_row(graph: dict, value: str, *, row_load_from_db: dict | None = None) -> dict:
    target = copy.deepcopy(graph)
    row = {"__id__": "r2", "__pos__": 2, "key": "Authorization", "value": value}
    if row_load_from_db is not None:
        row["__load_from_db_fields"] = row_load_from_db
    _template(target)["api_headers"]["value"].append(row)
    return target


def test_a_new_header_row_with_a_literal_token_reads_back_without_it():
    base = _docling()
    recorded = _record(base, _with_header_row(base, BEARER))

    operation, secrets, index = _write(recorded, HEADERS_ROW)

    # The whole row is one write; only its value cell is a secret.
    assert _parts(secrets, index) == [{"path": ["value"], "kind": "literal"}]
    read = _read(operation, secrets, index)
    assert read["value"] == {"__id__": "r2", "__pos__": 2, "key": "Authorization", "value": None}
    assert "secrets" not in read
    # The recorded operation keeps the token, so replay reproduces the flow.
    assert operation.updates[index].value["value"] == BEARER


def test_a_new_header_row_naming_a_known_variable_keeps_the_name():
    base = _docling()
    operation, secrets, index = _write(_record(base, _with_header_row(base, "DOCLING_TOKEN")), HEADERS_ROW)

    assert _parts(secrets, index) == [{"path": ["value"], "kind": "variable"}]
    assert _read(operation, secrets, index)["value"]["value"] == "DOCLING_TOKEN"
    # A variable the owner deleted since is no longer a name a read keeps.
    assert _read(operation, secrets, index, known=frozenset())["value"]["value"] is None


def test_a_new_header_row_naming_an_unknown_variable_reads_back_without_it():
    base = _docling()
    operation, secrets, index = _write(_record(base, _with_header_row(base, "NOT_A_VARIABLE")), HEADERS_ROW)

    assert _parts(secrets, index) == [{"path": ["value"], "kind": "literal"}]
    assert _read(operation, secrets, index)["value"]["value"] is None


def test_a_header_row_that_marks_its_value_as_a_literal_reads_back_without_it():
    base = _docling()
    target = _with_header_row(base, "DOCLING_TOKEN", row_load_from_db={"value": False})
    operation, secrets, index = _write(_record(base, target), HEADERS_ROW)

    assert _parts(secrets, index) == [{"path": ["value"], "kind": "literal"}]
    assert _read(operation, secrets, index)["value"]["value"] is None


def test_a_header_cell_write_is_stripped_by_the_row_it_lands_in():
    base = _with_header_row(_docling(), "DOCLING_TOKEN")
    target = copy.deepcopy(base)
    _template(target)["api_headers"]["value"][0]["value"] = BEARER
    cell = [*HEADERS_ROW, "value"]

    operation, secrets, index = _write(_record(base, target), cell)

    assert _parts(secrets, index) == [{"path": [], "kind": "literal"}]
    assert _read(operation, secrets, index)["value"] is None


def test_a_whole_header_table_write_names_its_rows_by_index():
    target = _with_header_row(_docling(), BEARER)
    rows = _template(target)["api_headers"]["value"]
    rows.insert(0, {"__id__": "r1", "__pos__": 1, "key": "Accept", "value": "application/json"})
    rows.append({"__id__": "r3", "__pos__": 3, "key": "X-Request-Source", "value": "DOCLING_TOKEN"})
    table = [*TEMPLATE, "api_headers", "value"]
    operation = parse_flow_operation(
        {"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": table, "value": rows}]}
    )

    secrets = SecretFinder(target, KNOWN_VARIABLES).secrets_of(operation)

    # A flow read hides every value cell that does not name one of the owner's variables, so the plain
    # Accept value is hidden too.
    assert _parts(secrets, 0) == [
        {"path": [0, "value"], "kind": "literal"},
        {"path": [1, "value"], "kind": "literal"},
        {"path": [2, "value"], "kind": "variable"},
    ]
    read = _read(operation, secrets, 0)["value"]
    assert [(row["key"], row["value"]) for row in read] == [
        ("Accept", None),
        ("Authorization", None),
        ("X-Request-Source", "DOCLING_TOKEN"),
    ]
    assert read == _template(strip_graph_secrets(target, KNOWN_VARIABLES))["api_headers"]["value"]


def test_a_dictionary_value_loses_only_its_secret_named_key():
    base = _docling()
    target = copy.deepcopy(base)
    _template(target)["docling_serve_opts"]["value"] = {"token": "abc123", "do_ocr": True}

    operation, secrets, index = _write(_record(base, target), [*TEMPLATE, "docling_serve_opts", "value"])

    assert _parts(secrets, index) == [{"path": ["token"], "kind": "literal"}]
    assert _read(operation, secrets, index)["value"] == {"token": None, "do_ocr": True}


def test_ordinary_values_have_no_secret_parts():
    base = _docling()
    target = copy.deepcopy(base)
    _template(target)["api_url"]["value"] = "http://localhost:5001"
    target["nodes"][0]["position"] = {"x": 3, "y": 4}

    ((operation, secrets),) = _record(base, target)

    assert all(parts == () for parts in secrets)
    read = strip_operation_secrets(operation, secrets, KNOWN_VARIABLES)
    assert read == operation.model_dump(mode="json")


# --- Password fields ----------------------------------------------------------------------


def test_a_pasted_aws_key_in_the_file_component_is_stripped():
    """``aws_access_key_id`` is a password field whose name the secret-name rule does not match."""
    flow = json.loads((STARTER_PROJECTS / "Financial Report Parser.json").read_text())["data"]
    target = copy.deepcopy(flow)
    file_node = next(node for node in target["nodes"] if node["id"] == "File-NGW2N")
    file_node["data"]["node"]["template"]["aws_access_key_id"]["value"] = AWS_KEY

    operation, secrets, index = _write(_record(flow, target), [*TEMPLATE, "aws_access_key_id", "value"])

    assert operation.updates[index].id == "File-NGW2N"
    assert _parts(secrets, index) == [{"path": [], "kind": "literal"}]
    assert _read(operation, secrets, index)["value"] is None


def _openai_node(api_key: dict | None = None, node_id: str = "a") -> dict:
    template = {"text": {"name": "text", "type": "str", "value": "hello"}}
    if api_key is not None:
        template["api_key"] = api_key
    return {"id": node_id, "position": {"x": 0, "y": 0}, "data": {"type": "OpenAI", "node": {"template": template}}}


def _api_key(value, *, load_from_db: bool = False) -> dict:
    return {"name": "api_key", "type": "str", "password": True, "load_from_db": load_from_db, "value": value}


def test_a_set_field_naming_a_known_variable_keeps_the_name():
    base = _graph(_openai_node(_api_key("OLD_KEY", load_from_db=True)))
    target = _graph(_openai_node(_api_key("OPENAI_API_KEY", load_from_db=True)))

    operation, secrets, index = _write(_record(base, target), [*TEMPLATE, "api_key", "value"])

    assert _parts(secrets, index) == [{"path": [], "kind": "variable"}]
    assert _read(operation, secrets, index)["value"] == "OPENAI_API_KEY"
    assert _read(operation, secrets, index, known=frozenset())["value"] is None


def test_a_whole_secret_field_set_at_once_keeps_its_definition():
    base = _graph(_openai_node())
    target = _graph(_openai_node(_api_key("sk-literal-secret")))

    operation, secrets, index = _write(_record(base, target), [*TEMPLATE, "api_key"])

    assert _parts(secrets, index) == [{"path": ["value"], "kind": "literal"}]
    read = _read(operation, secrets, index)["value"]
    assert read["value"] is None
    assert read["password"] is True


def test_added_nodes_lose_literal_secrets_and_keep_variable_names():
    first = _openai_node(_api_key("sk-literal-secret"))
    second = _openai_node(_api_key("OPENAI_API_KEY", load_from_db=True), node_id="b")
    ((add_nodes, secrets),) = _record(_graph(), _graph(first, second))

    stripped = strip_operation_secrets(add_nodes, secrets, KNOWN_VARIABLES)

    assert secrets == ()
    assert [node["data"]["node"]["template"]["api_key"]["value"] for node in stripped["nodes"]] == [
        None,
        "OPENAI_API_KEY",
    ]
    # Only the copy that leaves is stripped.
    assert add_nodes.nodes[0]["data"]["node"]["template"]["api_key"]["value"] == "sk-literal-secret"


# --- MCP Tools: a server value and its headers ---------------------------------------------


def test_an_mcp_server_value_keeps_only_its_name():
    server = {
        "name": "github",
        "config": {"command": "npx", "env": {"GITHUB_TOKEN": "ghp_literalsecret0123"}},  # pragma: allowlist secret
    }
    base = _graph(_component_node(MCPToolsComponent(), "a"))
    target = copy.deepcopy(base)
    _template(target)["mcp_server"]["value"] = server

    operation, secrets, index = _write(_record(base, target), [*TEMPLATE, "mcp_server", "value"])

    # The scrubbing removes the config, so a read removes it too, as a flow read does.
    assert _parts(secrets, index) == [{"path": ["config"], "kind": "removed"}]
    assert _read(operation, secrets, index)["value"] == {"name": "github"}
    assert strip_graph_secrets(target, KNOWN_VARIABLES)["nodes"][0]["data"]["node"]["template"]["mcp_server"][
        "value"
    ] == {"name": "github"}


def _mcp_headers_write(rows: list[dict]) -> tuple:
    """Record a Headers box in list form, next to an MCP server, and return the write and the flow read's value."""
    base = _graph(_component_node(MCPToolsComponent(), "a"))
    _template(base)["mcp_server"]["value"] = {"name": "github"}
    target = copy.deepcopy(base)
    _template(target)["headers"]["value"] = rows
    operation, secrets, index = _write(_record(base, target), [*TEMPLATE, "headers", "value"])
    flow_read = _template(strip_graph_secrets(target, KNOWN_VARIABLES))["headers"]["value"]
    return operation, secrets, index, flow_read


def test_an_mcp_headers_list_reads_back_as_a_flow_read_shows_it():
    rows = [
        {"key": "Authorization", "value": BEARER},
        {"key": "X-Tenant", "value": "acme"},
        {"key": "X-Tenant", "value": "acme-eu"},
    ]
    operation, secrets, index, flow_read = _mcp_headers_write(rows)

    # Only the secret header is hidden; the plain headers stay, as in a flow read.
    assert _parts(secrets, index) == [{"path": [0, "value"], "kind": "literal"}]
    read = _read(operation, secrets, index)["value"]
    assert read == flow_read
    assert read == [
        {"key": "Authorization", "value": None},
        {"key": "X-Tenant", "value": "acme"},
        {"key": "X-Tenant", "value": "acme-eu"},
    ]


def test_a_list_with_repeated_item_keys_stores_normally():
    rows = [{"key": "Authorization", "value": BEARER}, {"key": "Authorization", "value": "Bearer second-0123456789"}]
    operation, secrets, index, flow_read = _mcp_headers_write(rows)

    assert _parts(secrets, index) == [
        {"path": [0, "value"], "kind": "literal"},
        {"path": [1, "value"], "kind": "literal"},
    ]
    assert _read(operation, secrets, index)["value"] == flow_read


# --- A value that equals a variable name -------------------------------------------------


def _language_model(node_id: str, api_key: str, *, load_from_db: bool, system_message: str = "") -> dict:
    node = _component_node(LanguageModelComponent(), node_id)
    template = node["data"]["node"]["template"]
    template["api_key"]["value"] = api_key
    template["api_key"]["load_from_db"] = load_from_db
    template["system_message"]["value"] = system_message
    return node


def test_text_equal_to_a_kept_variable_name_is_not_a_secret():
    """The scrubbing keeps the prompt text because it is not a secret, not because it names a variable."""
    base = _graph(_language_model("a", "OPENAI_API_KEY", load_from_db=True, system_message="hello"))
    target = _graph(_language_model("a", "OPENAI_API_KEY", load_from_db=True, system_message="OPENAI_API_KEY"))

    operation, secrets, index = _write(_record(base, target), [*TEMPLATE, "system_message", "value"])

    assert _parts(secrets, index) == []
    # The owner deleted the variable since: a flow read keeps the text, and so does the history.
    assert _read(operation, secrets, index, known=frozenset())["value"] == "OPENAI_API_KEY"


def test_a_field_without_a_value_has_no_secret_parts():
    """The scrubbing gives the field a null value, which hides nothing."""
    target = _graph(_language_model("a", "", load_from_db=False))
    base = copy.deepcopy(target)
    del _template(base)["model"]

    operation, secrets, index = _write(_record(base, target), [*TEMPLATE, "model"])

    assert "value" not in operation.updates[index].value
    assert _parts(secrets, index) == []


# --- A group's sub-flow ---------------------------------------------------------------------

FLOW = ["data", "node", "flow"]
INNER_API_KEY = ["data", "node", "template", "api_key", "value"]


def _group(node_id: str, *inner: dict) -> dict:
    """A group node as the editor saves it: the grouped nodes and their edges are its sub-flow."""
    edges = [
        {"id": f"edge-{source['id']}-{target['id']}", "source": source["id"], "target": target["id"], "data": {}}
        for source, target in itertools.pairwise(inner)
    ]
    flow = {"data": {"nodes": list(inner), "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 1}}, "name": "Group"}
    return {
        "id": node_id,
        "type": "genericNode",
        "position": {"x": 0, "y": 0},
        "data": {"id": node_id, "type": "GroupNode", "node": {"display_name": "Group", "template": {}, "flow": flow}},
    }


def _chat_input(node_id: str = "chat") -> dict:
    return _component_node(ChatInput(), node_id)


def _sub_flow(graph: dict) -> dict:
    return graph["nodes"][0]["data"]["node"]["flow"]


def test_a_secret_in_a_group_names_the_inner_field():
    base = _graph(_group("g", _chat_input(), _language_model("lm", "", load_from_db=False)))
    target = _graph(_group("g", _chat_input(), _language_model("lm", "sk-literal-secret", load_from_db=False)))

    operation, secrets, index = _write(_record(base, target), FLOW)

    # The sub-flow is written whole; the secret part names the inner node by its index.
    assert _parts(secrets, index) == [{"path": ["data", "nodes", 1, *INNER_API_KEY], "kind": "literal"}]
    read = _read(operation, secrets, index)["value"]
    expected = copy.deepcopy(_sub_flow(target))
    expected["data"]["nodes"][1]["data"]["node"]["template"]["api_key"]["value"] = None
    assert read == expected
    assert operation.updates[index].value["data"]["nodes"][1]["data"]["node"]["template"]["api_key"]["value"] == (
        "sk-literal-secret"
    )


def test_a_variable_in_a_group_is_kept_while_it_exists():
    base = _graph(_group("g", _chat_input(), _language_model("lm", "", load_from_db=False)))
    inner = _language_model("lm", "OPENAI_API_KEY", load_from_db=True, system_message="OPENAI_API_KEY")
    target = _graph(_group("g", _chat_input(), inner))

    operation, secrets, index = _write(_record(base, target), FLOW)

    # Only the bound field is a variable part; the prompt text that spells the name is not.
    assert _parts(secrets, index) == [{"path": ["data", "nodes", 1, *INNER_API_KEY], "kind": "variable"}]
    kept = _read(operation, secrets, index)["value"]["data"]["nodes"][1]["data"]["node"]["template"]
    assert (kept["api_key"]["value"], kept["system_message"]["value"]) == ("OPENAI_API_KEY", "OPENAI_API_KEY")
    gone = _read(operation, secrets, index, known=frozenset())["value"]["data"]["nodes"][1]["data"]["node"]["template"]
    assert (gone["api_key"]["value"], gone["system_message"]["value"]) == (None, "OPENAI_API_KEY")


def test_a_secret_in_a_nested_group_names_each_level():
    def graph(api_key: str) -> dict:
        inner_group = _group("inner", _chat_input(), _language_model("lm", api_key, load_from_db=False))
        return _graph(_group("g", _chat_input("outer-chat"), inner_group))

    base, target = graph(""), graph("sk-literal-secret")

    operation, secrets, index = _write(_record(base, target), FLOW)

    path = ["data", "nodes", 1, *FLOW, "data", "nodes", 1, *INNER_API_KEY]
    assert _parts(secrets, index) == [{"path": path, "kind": "literal"}]
    read = _read(operation, secrets, index)["value"]
    expected = copy.deepcopy(_sub_flow(target))
    inner_group = expected["data"]["nodes"][1]
    inner_group["data"]["node"]["flow"]["data"]["nodes"][1]["data"]["node"]["template"]["api_key"]["value"] = None
    assert read == expected


# --- Refusals -----------------------------------------------------------------------------


def test_a_write_the_graph_after_the_batch_does_not_hold_is_refused():
    graph = _graph(_openai_node(_api_key("sk-literal-secret")))
    path = [*TEMPLATE, "api_key", "value"]
    operation = parse_flow_operation(
        {"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": path, "value": "x"}]}
    )

    with pytest.raises(ValueError, match="does not hold the value written"):
        SecretFinder(graph, KNOWN_VARIABLES).secrets_of(operation)


@pytest.mark.parametrize(
    "raw",
    [
        {"path": [], "kind": "mcp"},
        {"path": [{"key": "lm"}], "kind": "literal"},
        {"path": [-1], "kind": "literal"},
        {"path": [True], "kind": "literal"},
        {"path": [1.0], "kind": "literal"},
        {"path": [None], "kind": "literal"},
        {"path": "value", "kind": "literal"},
        {"path": [], "kind": "literal", "extra": 1},
    ],
)
def test_a_malformed_stored_part_is_refused(raw):
    with pytest.raises(ValueError):  # noqa: PT011 - each case fails a different check
        SecretPart.from_json(raw)


def test_reconstructed_graphs_are_stripped_without_touching_the_original():
    graph = _graph(_openai_node(_api_key("sk-literal-secret")))

    stripped = strip_graph_secrets(graph, KNOWN_VARIABLES)

    assert _template(stripped)["api_key"]["value"] is None
    assert _template(graph)["api_key"]["value"] == "sk-literal-secret"
