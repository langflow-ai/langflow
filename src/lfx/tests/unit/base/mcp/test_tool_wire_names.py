"""MCP tool calls must reach the server under the server's own property names.

Pydantic cannot declare a field named ``_user_goal``, so the input model sanitizes it to
``user_goal``. The call must still send ``_user_goal``, or the server never receives it.
"""

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


async def test_tool_coroutine_sends_wire_property_names():
    client = _RecordingClient()
    tool = create_tool_coroutine("search", create_input_schema_from_json_schema(SCHEMA), client)

    await tool(**FIELD_ARGS)

    assert client.calls == [WIRE_ARGS]


def test_tool_func_sends_wire_property_names():
    client = _RecordingClient()
    tool = create_tool_func("search", create_input_schema_from_json_schema(SCHEMA), client)

    tool(**FIELD_ARGS)

    assert client.calls == [WIRE_ARGS]
