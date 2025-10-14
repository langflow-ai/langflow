"""Test MCP payload sanitization and optional parameter handling."""

import types
from typing import Any

import pytest
from pydantic import BaseModel

from lfx.base.mcp.util import create_tool_coroutine
from lfx.schema.json_schema import create_input_schema_from_json_schema


class CapturingClient:
    """Mock MCP client that captures arguments for testing."""

    def __init__(self):
        self.args: dict[str, Any] | None = None

    async def run_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.args = arguments
        # Return a minimal result object
        return types.SimpleNamespace(content=[])


def build_args_schema(schema: dict[str, Any]) -> type[BaseModel]:
    """Build a Pydantic schema from JSON Schema."""
    return create_input_schema_from_json_schema(schema)


@pytest.mark.asyncio
async def test_optional_enum_blank_is_omitted():
    """Test that blank optional enum parameters are omitted from the payload."""
    schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "engine": {
                "type": "string",
                "enum": ["google", "bing", "yandex"],
                "default": "google",
            },
        },
        "required": ["query"],
    }
    args_schema = build_args_schema(schema)
    client = CapturingClient()
    coro = create_tool_coroutine("search_engine", args_schema, client)

    # Call with blank engine parameter
    await coro(query="hello", engine="")

    # engine should be omitted, allowing server default to apply
    assert client.args == {"query": "hello"}


@pytest.mark.asyncio
async def test_optional_none_is_omitted_and_nested_nones_removed():
    """Test that None optional parameters are omitted and nested Nones are removed."""
    schema = {
        "type": "object",
        "properties": {
            "uid": {"type": "string"},
            "flags": {
                "type": "object",
                "properties": {"a": {"type": "string"}},
            },
        },
        "required": ["uid"],
    }
    args_schema = build_args_schema(schema)
    client = CapturingClient()
    coro = create_tool_coroutine("click", args_schema, client)

    # Call with None flags parameter
    await coro(uid="1_67", flags=None)

    # flags should be omitted
    assert client.args == {"uid": "1_67"}


@pytest.mark.asyncio
async def test_required_params_are_included():
    """Test that required parameters are always included even if empty."""
    schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["query", "limit"],
    }
    args_schema = build_args_schema(schema)
    client = CapturingClient()
    coro = create_tool_coroutine("search", args_schema, client)

    # Call with empty query (required field)
    await coro(query="", limit=10)

    # Required field should be included even if empty
    assert client.args == {"query": "", "limit": 10}


@pytest.mark.asyncio
async def test_optional_with_value_is_included():
    """Test that optional parameters with actual values are included."""
    schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "engine": {"type": "string", "enum": ["google", "bing"]},
        },
        "required": ["query"],
    }
    args_schema = build_args_schema(schema)
    client = CapturingClient()
    coro = create_tool_coroutine("search_engine", args_schema, client)

    # Call with actual engine value
    await coro(query="hello", engine="bing")

    # Both should be included
    assert client.args == {"query": "hello", "engine": "bing"}


@pytest.mark.asyncio
async def test_empty_list_is_omitted():
    """Test that empty list optional parameters are omitted."""
    schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "filters": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["query"],
    }
    args_schema = build_args_schema(schema)
    client = CapturingClient()
    coro = create_tool_coroutine("search", args_schema, client)

    # Call with empty list
    await coro(query="hello", filters=[])

    # Empty list should be omitted
    assert client.args == {"query": "hello"}


@pytest.mark.asyncio
async def test_empty_dict_is_omitted():
    """Test that empty dict optional parameters are omitted."""
    schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "metadata": {"type": "object"},
        },
        "required": ["query"],
    }
    args_schema = build_args_schema(schema)
    client = CapturingClient()
    coro = create_tool_coroutine("search", args_schema, client)

    # Call with empty dict
    await coro(query="hello", metadata={})

    # Empty dict should be omitted
    assert client.args == {"query": "hello"}


@pytest.mark.asyncio
async def test_whitespace_only_string_is_omitted():
    """Test that whitespace-only string optional parameters are omitted."""
    schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "filter": {"type": "string"},
        },
        "required": ["query"],
    }
    args_schema = build_args_schema(schema)
    client = CapturingClient()
    coro = create_tool_coroutine("search", args_schema, client)

    # Call with whitespace-only filter
    await coro(query="hello", filter="   ")

    # Whitespace-only filter should be omitted
    assert client.args == {"query": "hello"}
