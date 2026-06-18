"""Unit tests for ToolWrapperInputHandler and its pure helpers.

Real-component execution is covered in ``test_tool_wrapper_execution.py``; this
file covers the calculator fast-path, schema/blob reshaping helpers, ``matches``,
and failed-wrapper handling, none of which need a running component.
"""

import pytest
from langchain_core.tools import StructuredTool

from langflow_stepflow.worker.handlers.tool_wrapper import (
    ToolWrapperInputHandler,
    _build_blob_data,
    _build_input_schema,
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


def _calculator_wrapper() -> dict:
    return _make_tool_wrapper(
        name="evaluate_expression",
        properties={"expression": {"type": "string", "default": ""}},
    )


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
        assert "Calculator error" in _execute_calculator_tool("not_valid")

    def test_division_by_zero(self):
        assert "Calculator error" in _execute_calculator_tool("1 / 0")


# ---------------------------------------------------------------------------
# _build_blob_data
# ---------------------------------------------------------------------------


class TestBuildBlobData:
    def test_reshapes_raw_component_into_enhanced_blob(self):
        node_info = {
            "template": {
                "code": {"value": "print('x')"},
                "text_input": {"type": "str", "value": "hi"},
            },
            "outputs": [{"name": "result", "method": "process_text"}],
            "display_name": "My Comp",
        }

        blob = _build_blob_data(node_info, "MyComponent")

        assert blob["code"] == "print('x')"
        # Code is lifted to the top level and dropped from the template.
        assert "code" not in blob["template"]
        assert blob["template"]["text_input"]["value"] == "hi"
        assert blob["component_type"] == "MyComponent"
        assert blob["outputs"] == [{"name": "result", "method": "process_text"}]
        assert blob["selected_output"] == "result"
        assert blob["display_name"] == "My Comp"

    def test_no_outputs_yields_none_selected_output(self):
        blob = _build_blob_data({"template": {"code": {"value": "x"}}}, "C")
        assert blob["selected_output"] is None
        # component_type is the display_name fallback.
        assert blob["display_name"] == "C"


# ---------------------------------------------------------------------------
# _build_input_schema
# ---------------------------------------------------------------------------


class TestBuildInputSchema:
    def test_builds_model_with_declared_properties(self):
        schema = _build_input_schema({"properties": {"query": {"default": ""}, "limit": {"default": "10"}}})
        instance = schema(query="a", limit="b")
        assert instance.query == "a"
        assert instance.limit == "b"

    def test_default_values_applied(self):
        schema = _build_input_schema({"properties": {"limit": {"default": "10"}}})
        assert schema().limit == "10"

    def test_empty_properties_yields_constructible_schema(self):
        schema = _build_input_schema({})
        assert schema() is not None


# ---------------------------------------------------------------------------
# _create_tool_from_wrapper
# ---------------------------------------------------------------------------


class TestCreateToolFromWrapper:
    @pytest.mark.asyncio
    async def test_calculator_tool_creates_structured_tool(self):
        tool = await _create_tool_from_wrapper(_calculator_wrapper())
        assert isinstance(tool, StructuredTool)
        assert tool.name == "evaluate_expression"

    @pytest.mark.asyncio
    async def test_calculator_tool_execution(self):
        tool = await _create_tool_from_wrapper(_calculator_wrapper())
        result = await tool.ainvoke({"expression": "2 + 3"})
        assert result == {"result": "5"}

    @pytest.mark.asyncio
    async def test_missing_both_code_sources_returns_failed_wrapper(self):
        wrapper = _make_tool_wrapper(component_code=None, code_blob_id=None)
        tool = await _create_tool_from_wrapper(wrapper)

        assert not isinstance(tool, StructuredTool)
        assert tool.name == "test_tool"
        result = tool.invoke({})
        assert "Tool creation failed" in result["error"]

    @pytest.mark.asyncio
    async def test_code_blob_id_without_context_returns_failed_wrapper(self):
        # The real-execution path needs a context to fetch the component blob;
        # without one the wrapper degrades to a failed tool rather than faking a result.
        wrapper = _make_tool_wrapper(component_code=None, code_blob_id="abc123")
        tool = await _create_tool_from_wrapper(wrapper, context=None)

        assert not isinstance(tool, StructuredTool)
        result = tool.invoke({})
        assert "Tool creation failed" in result["error"]


# ---------------------------------------------------------------------------
# ToolWrapperInputHandler.matches
# ---------------------------------------------------------------------------


class TestToolWrapperInputHandlerMatches:
    def setup_method(self):
        self.handler = ToolWrapperInputHandler()

    def test_matches_dict_with_tool_wrapper_marker(self):
        assert self.handler.matches(template_field={}, value=_make_tool_wrapper()) is True

    def test_matches_list_with_tool_wrapper(self):
        assert self.handler.matches(template_field={}, value=[_make_tool_wrapper()]) is True

    def test_matches_list_with_mixed_items(self):
        assert self.handler.matches(template_field={}, value=[_make_tool_wrapper(), "other"]) is True

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
# ToolWrapperInputHandler.prepare (no-context paths)
# ---------------------------------------------------------------------------


class TestToolWrapperInputHandlerPrepare:
    def setup_method(self):
        self.handler = ToolWrapperInputHandler()

    @pytest.mark.asyncio
    async def test_prepare_calculator_wrapper_without_context(self):
        result = await self.handler.prepare({"tools": (_calculator_wrapper(), {})}, None)
        assert isinstance(result["tools"], StructuredTool)
        assert result["tools"].name == "evaluate_expression"

    @pytest.mark.asyncio
    async def test_prepare_failed_wrapper_in_list(self):
        good = _calculator_wrapper()
        bad = _make_tool_wrapper(name="bad_tool", component_code=None, code_blob_id=None)
        result = await self.handler.prepare({"tools": ([good, bad], {})}, None)

        assert isinstance(result["tools"][0], StructuredTool)
        assert not isinstance(result["tools"][1], StructuredTool)
        assert result["tools"][1].name == "bad_tool"
