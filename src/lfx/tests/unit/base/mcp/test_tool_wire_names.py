"""MCP tool calls must reach the server under the server's own property names.

Pydantic cannot declare a field named ``_user_goal``, so the input model sanitizes it to
``user_goal``. The call must still send ``_user_goal``, or the server never receives it.
"""

import pytest
from lfx.base.mcp.util import create_tool_coroutine, create_tool_func
from lfx.schema.json_schema import create_input_schema_from_json_schema

SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "_user_goal": {"type": "string"},
        "opts": {"type": "object", "properties": {"_trace_id": {"type": "string"}, "page_size": {"type": "integer"}}},
    },
    "required": ["query", "_user_goal"],
}
FIELD_ARGS = {"query": "q", "user_goal": "g", "opts": {"trace_id": "t", "page_size": 5}}
WIRE_ARGS = {"query": "q", "_user_goal": "g", "opts": {"_trace_id": "t", "page_size": 5}}


class _RecordingClient:
    def __init__(self):
        self.calls: list[dict] = []

    async def run_tool(self, tool_name, arguments):  # noqa: ARG002
        self.calls.append(arguments)


@pytest.mark.parametrize("arguments", [FIELD_ARGS, WIRE_ARGS])
@pytest.mark.parametrize("allow_extras", [True, False])
async def test_tool_coroutine_sends_wire_property_names(arguments, allow_extras):
    client = _RecordingClient()
    schema = create_input_schema_from_json_schema({**SCHEMA, "additionalProperties": allow_extras})
    tool = create_tool_coroutine("search", schema, client)

    await tool(**arguments)

    assert client.calls == [WIRE_ARGS]


@pytest.mark.parametrize("arguments", [FIELD_ARGS, WIRE_ARGS])
@pytest.mark.parametrize("allow_extras", [True, False])
def test_tool_func_sends_wire_property_names(arguments, allow_extras):
    client = _RecordingClient()
    schema = create_input_schema_from_json_schema({**SCHEMA, "additionalProperties": allow_extras})
    tool = create_tool_func("search", schema, client)

    tool(**arguments)

    assert client.calls == [WIRE_ARGS]


@pytest.mark.parametrize("use_async", [True, False])
@pytest.mark.parametrize("alias", ["item_count", "_item_count", "_itemCount"])
async def test_tool_converts_wire_alias_values_before_validation(use_async, alias):
    schema = create_input_schema_from_json_schema(
        {
            "type": "object",
            "properties": {"_item_count": {"type": "integer"}},
            "required": ["_item_count"],
            "additionalProperties": False,
        }
    )
    client = _RecordingClient()
    factory = create_tool_coroutine if use_async else create_tool_func
    tool = factory("search", schema, client)

    if use_async:
        await tool(**{alias: "3"})
    else:
        tool(**{alias: "3"})

    assert client.calls == [{"_item_count": 3}]


@pytest.mark.parametrize("use_async", [True, False])
@pytest.mark.parametrize("wire_first", [True, False])
async def test_tool_prefers_field_value_without_leaking_duplicate_wire_alias(use_async, wire_first):
    schema = create_input_schema_from_json_schema(SCHEMA)
    arguments = {"_user_goal": "alternate", "user_goal": "preferred", "query": "q"}
    if not wire_first:
        arguments = dict(reversed(arguments.items()))
    client = _RecordingClient()
    factory = create_tool_coroutine if use_async else create_tool_func
    tool = factory("search", schema, client)

    if use_async:
        await tool(**arguments)
    else:
        tool(**arguments)

    assert client.calls == [{"query": "q", "_user_goal": "preferred"}]


@pytest.mark.parametrize("use_async", [True, False])
async def test_tool_keeps_colliding_properties_distinct(use_async):
    schema = create_input_schema_from_json_schema(
        {
            "type": "object",
            "properties": {"_foo": {"type": "string"}, "foo": {"type": "string"}},
            "required": ["_foo", "foo"],
        }
    )
    client = _RecordingClient()
    factory = create_tool_coroutine if use_async else create_tool_func
    tool = factory("search", schema, client)

    if use_async:
        await tool(_foo="private", foo="public")
    else:
        tool(_foo="private", foo="public")

    assert client.calls == [{"_foo": "private", "foo": "public"}]
