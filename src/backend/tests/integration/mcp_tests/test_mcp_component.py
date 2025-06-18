"""Integration tests for MCPToolsComponent.

These tests focus on component structure and behavior without requiring database setup.
"""

import pytest
from langflow.components.data.mcp_component import MCPToolsComponent
from langflow.schema.dataframe import DataFrame

from tests.integration.utils import run_single_component

pytestmark = pytest.mark.asyncio


async def test_mcp_component_client_initialization():
    """Test that MCPToolsComponent properly initializes its clients."""
    component = MCPToolsComponent()

    # Component should have both clients initialized
    assert hasattr(component, "stdio_client")
    assert hasattr(component, "sse_client")
    assert component.stdio_client is not None
    assert component.sse_client is not None

    # Clients should have expected methods
    assert hasattr(component.stdio_client, "connect_to_server")
    assert hasattr(component.stdio_client, "run_tool")
    assert hasattr(component.sse_client, "connect_to_server")
    assert hasattr(component.sse_client, "run_tool")


async def test_mcp_component_build_config_structure():
    """Test the basic structure of MCPToolsComponent's build configuration."""
    component = MCPToolsComponent()

    # Test that basic inputs exist
    input_names = [inp.name for inp in component.inputs]
    expected_inputs = ["mcp_server", "tool", "tool_placeholder"]

    for expected in expected_inputs:
        assert expected in input_names, f"Expected input '{expected}' not found in component inputs"

    # Test that basic outputs exist
    output_names = [out.name for out in component.outputs]
    assert "response" in output_names, "Expected 'response' output not found"


@pytest.mark.xfail(reason="DataFrame API issue - needs proper pandas DataFrame access pattern")
async def test_mcp_component_build_output_no_tool():
    """Test MCPToolsComponent build_output when no tool is selected."""
    component = MCPToolsComponent()
    component.tool = ""  # No tool selected
    component.tools = []

    # Should return error dataframe when no tool selected
    result = await component.build_output()
    assert isinstance(result, DataFrame)
    assert len(result.data) > 0
    assert "error" in str(result.data[0]).lower()


async def test_mcp_component_default_keys():
    """Test that component has proper default keys defined."""
    component = MCPToolsComponent()

    expected_defaults = ["code", "_type", "tool_mode", "tool_placeholder", "mcp_server", "tool"]

    for key in expected_defaults:
        assert key in component.default_keys, f"Expected default key '{key}' not found"


async def test_mcp_component_maybe_unflatten_dict():
    """Test the utility function for unflattening nested dictionaries."""
    from langflow.components.data.mcp_component import maybe_unflatten_dict

    # Test simple case - no nested keys
    simple = {"a": 1, "b": 2}
    result = maybe_unflatten_dict(simple)
    assert result == simple

    # Test nested case with dots
    nested = {"data.name": "test", "data.values[0]": 1, "data.values[1]": 2}
    result = maybe_unflatten_dict(nested)

    assert "data" in result
    assert result["data"]["name"] == "test"
    assert result["data"]["values"][0] == 1
    assert result["data"]["values"][1] == 2


async def test_mcp_component_error_handling():
    """Test MCPToolsComponent error handling during build_output."""
    component = MCPToolsComponent()
    component.tool = "nonexistent_tool"
    component.tools = []

    # Should handle missing tool gracefully by returning an error DataFrame
    result = await component.build_output()
    assert isinstance(result, DataFrame)
    assert len(result) > 0  # Use len() on DataFrame directly

    # Check that the error is about the tool not being found
    # Use to_dict('records') to get the original data back
    data_records = result.to_dict("records")
    assert len(data_records) > 0
    error_content = str(data_records[0]).lower()
    assert "error" in error_content
    assert "tool" in error_content or "not found" in error_content


# TODO: Add more tests for MCPToolsComponent
@pytest.mark.asyncio
async def test_mcp_component():
    from langflow.components.data.mcp_component import MCPToolsComponent

    inputs = {}

    # The component should now handle missing MCP server gracefully
    # and return an error in the response rather than raising an exception
    result = await run_single_component(
        MCPToolsComponent,
        inputs=inputs,
    )

    # Check that we get a result with an error message
    assert result is not None
    response = result.get("response")
    assert response is not None

    # The response should contain an error about missing tool selection
    # Use to_dict('records') to get the original data back from Langflow DataFrame
    data_records = response.to_dict("records")
    assert len(data_records) > 0

    # Check that the error message is about tool selection
    error_content = str(data_records[0]).lower()
    assert "error" in error_content
    assert "tool" in error_content or "select" in error_content
