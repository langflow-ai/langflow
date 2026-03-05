"""Unit tests for ToolWrapperInputHandler."""

import pytest
from langchain_core.tools import StructuredTool

from langflow_stepflow.worker.handlers.tool_wrapper import (
    ToolWrapperInputHandler,
    _create_tool_from_wrapper,
    _execute_calculator_tool,
)


def _make_tool_wrapper(
    *,
    name: str = "test_tool",
    description: str = "A test tool",
    component_code: str | None = "print('hello')",
    code_blob_id: str | None = None,
    properties: dict | None = None,
    static_inputs: dict | None = None,
    component_type: str = "TestComponent",
    session_id: str = "test_session",
) -> dict:
    """Create a tool wrapper dict for testing."""
    wrapper: dict = {
        "__tool_wrapper__": True,
        "tool_metadata": {"name": name, "description": description},
        "tool_input_schema": {"properties": properties or {}},
        "static_inputs": static_inputs or {},
        "component_type": component_type,
        "session_id": session_id,
    }
    if component_code is not None:
        wrapper["component_code"] = component_code
    if code_blob_id is not None:
        wrapper["code_blob_id"] = code_blob_id
    return wrapper


# ---------------------------------------------------------------------------
# _execute_calculator_tool
# ---------------------------------------------------------------------------


class TestExecuteCalculatorTool:
    def test_simple_addition(self):
        assert _execute_calculator_tool("2 + 3") == "5"

    def test_multiplication(self):
        assert _execute_calculator_tool("6 * 7") == "42"

    def test_division(self):
        assert _execute_calculator_tool("10 / 4") == "2.5"

    def test_power(self):
        assert _execute_calculator_tool("2 ** 10") == "1024"

    def test_complex_expression(self):
        assert _execute_calculator_tool("(2 + 3) * 4") == "20"

    def test_float_result(self):
        assert _execute_calculator_tool("1 / 3") == "0.333333"

    def test_invalid_expression(self):
        result = _execute_calculator_tool("not_valid")
        assert "Calculator error" in result

    def test_division_by_zero(self):
        result = _execute_calculator_tool("1 / 0")
        assert "Calculator error" in result


# ---------------------------------------------------------------------------
# _create_tool_from_wrapper
# ---------------------------------------------------------------------------


class TestCreateToolFromWrapper:
    def test_creates_structured_tool(self):
        wrapper = _make_tool_wrapper(name="my_tool", description="does stuff")
        tool = _create_tool_from_wrapper(wrapper)

        assert isinstance(tool, StructuredTool)
        assert tool.name == "my_tool"
        assert tool.description == "does stuff"

    def test_creates_tool_with_code_blob_id(self):
        wrapper = _make_tool_wrapper(
            component_code=None,
            code_blob_id="abc123",
        )
        tool = _create_tool_from_wrapper(wrapper)
        assert isinstance(tool, StructuredTool)

    def test_tool_with_input_schema(self):
        wrapper = _make_tool_wrapper(
            properties={
                "query": {"type": "string", "default": ""},
                "limit": {"type": "integer", "default": "10"},
            },
        )
        tool = _create_tool_from_wrapper(wrapper)
        assert isinstance(tool, StructuredTool)

    def test_calculator_tool_execution(self):
        wrapper = _make_tool_wrapper(
            name="evaluate_expression",
            properties={"expression": {"type": "string", "default": ""}},
        )
        tool = _create_tool_from_wrapper(wrapper)
        result = tool.invoke({"expression": "2 + 3"})
        assert result == {"result": "5"}

    def test_non_calculator_tool_execution(self):
        wrapper = _make_tool_wrapper(
            name="search_tool",
            properties={"query": {"type": "string", "default": ""}},
            static_inputs={"api_key": "test_key"},
            component_type="SearchComponent",
            session_id="sess_1",
        )
        tool = _create_tool_from_wrapper(wrapper)
        result = tool.invoke({"query": "hello"})

        assert result["component_type"] == "SearchComponent"
        assert result["inputs"]["query"] == "hello"
        assert result["inputs"]["api_key"] == "test_key"
        assert result["inputs"]["session_id"] == "sess_1"
        assert result["status"] == "tool_wrapper_execution"

    def test_tool_with_code_blob_id_in_result(self):
        wrapper = _make_tool_wrapper(
            name="blob_tool",
            component_code=None,
            code_blob_id="blob_abc",
        )
        tool = _create_tool_from_wrapper(wrapper)
        result = tool.invoke({})
        assert result["code_blob_id"] == "blob_abc"

    def test_tool_with_component_code_in_result(self):
        wrapper = _make_tool_wrapper(
            name="code_tool",
            component_code="def run(): pass",
        )
        tool = _create_tool_from_wrapper(wrapper)
        result = tool.invoke({})
        assert result["has_component_code"] is True

    def test_missing_both_code_sources_returns_failed_wrapper(self):
        wrapper = _make_tool_wrapper(component_code=None, code_blob_id=None)
        tool = _create_tool_from_wrapper(wrapper)

        # Should be a FailedToolWrapper, not a StructuredTool
        assert not isinstance(tool, StructuredTool)
        assert hasattr(tool, "name")
        assert tool.name == "test_tool"
        result = tool.invoke({})
        assert "error" in result
        assert "Tool creation failed" in result["error"]


# ---------------------------------------------------------------------------
# ToolWrapperInputHandler.matches
# ---------------------------------------------------------------------------


class TestToolWrapperInputHandlerMatches:
    def setup_method(self):
        self.handler = ToolWrapperInputHandler()

    def test_matches_dict_with_tool_wrapper_marker(self):
        wrapper = _make_tool_wrapper()
        assert self.handler.matches(template_field={}, value=wrapper) is True

    def test_matches_list_with_tool_wrapper(self):
        wrapper = _make_tool_wrapper()
        assert self.handler.matches(template_field={}, value=[wrapper]) is True

    def test_matches_list_with_mixed_items(self):
        wrapper = _make_tool_wrapper()
        assert self.handler.matches(template_field={}, value=[wrapper, "other"]) is True

    def test_no_match_plain_dict(self):
        assert self.handler.matches(template_field={}, value={"key": "value"}) is False

    def test_no_match_dict_with_false_marker(self):
        assert self.handler.matches(template_field={}, value={"__tool_wrapper__": False}) is False

    def test_no_match_string(self):
        assert self.handler.matches(template_field={}, value="hello") is False

    def test_no_match_empty_list(self):
        assert self.handler.matches(template_field={}, value=[]) is False

    def test_no_match_list_without_wrappers(self):
        assert self.handler.matches(template_field={}, value=["a", "b", 42]) is False

    def test_no_match_none(self):
        assert self.handler.matches(template_field={}, value=None) is False


# ---------------------------------------------------------------------------
# ToolWrapperInputHandler.prepare
# ---------------------------------------------------------------------------


class TestToolWrapperInputHandlerPrepare:
    def setup_method(self):
        self.handler = ToolWrapperInputHandler()

    @pytest.mark.asyncio
    async def test_prepare_single_wrapper(self):
        wrapper = _make_tool_wrapper(name="my_tool")
        fields = {"tools": (wrapper, {})}
        result = await self.handler.prepare(fields, None)

        assert "tools" in result
        assert isinstance(result["tools"], StructuredTool)
        assert result["tools"].name == "my_tool"

    @pytest.mark.asyncio
    async def test_prepare_list_of_wrappers(self):
        wrapper_a = _make_tool_wrapper(name="tool_a")
        wrapper_b = _make_tool_wrapper(name="tool_b")
        fields = {"tools": ([wrapper_a, wrapper_b], {})}
        result = await self.handler.prepare(fields, None)

        assert "tools" in result
        assert len(result["tools"]) == 2
        assert isinstance(result["tools"][0], StructuredTool)
        assert isinstance(result["tools"][1], StructuredTool)
        assert result["tools"][0].name == "tool_a"
        assert result["tools"][1].name == "tool_b"

    @pytest.mark.asyncio
    async def test_prepare_mixed_list(self):
        wrapper = _make_tool_wrapper(name="real_tool")
        fields = {"tools": ([wrapper, "not_a_wrapper", 42], {})}
        result = await self.handler.prepare(fields, None)

        assert "tools" in result
        assert len(result["tools"]) == 3
        assert isinstance(result["tools"][0], StructuredTool)
        assert result["tools"][1] == "not_a_wrapper"
        assert result["tools"][2] == 42

    @pytest.mark.asyncio
    async def test_prepare_multiple_fields(self):
        wrapper_a = _make_tool_wrapper(name="tool_a")
        wrapper_b = _make_tool_wrapper(name="tool_b")
        fields = {
            "primary_tool": (wrapper_a, {}),
            "secondary_tool": (wrapper_b, {}),
        }
        result = await self.handler.prepare(fields, None)

        assert isinstance(result["primary_tool"], StructuredTool)
        assert isinstance(result["secondary_tool"], StructuredTool)
        assert result["primary_tool"].name == "tool_a"
        assert result["secondary_tool"].name == "tool_b"

    @pytest.mark.asyncio
    async def test_prepare_failed_wrapper_in_list(self):
        good_wrapper = _make_tool_wrapper(name="good_tool")
        bad_wrapper = _make_tool_wrapper(name="bad_tool", component_code=None, code_blob_id=None)
        fields = {"tools": ([good_wrapper, bad_wrapper], {})}
        result = await self.handler.prepare(fields, None)

        assert isinstance(result["tools"][0], StructuredTool)
        # Bad wrapper becomes FailedToolWrapper
        assert not isinstance(result["tools"][1], StructuredTool)
        assert result["tools"][1].name == "bad_tool"
