"""Tests for MCP component output processing."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from lfx.components.models_and_agents.mcp_component import MCPToolsComponent
from lfx.schema.dataframe import DataFrame


class TestMCPComponentOutputProcessing:
    """Test MCP component output processing, particularly for DataFrame compatibility."""

    @pytest.fixture
    def component(self):
        """Create an MCP component for testing."""
        return MCPToolsComponent()

    def test_process_output_item_with_dict_json(self, component):
        """Test that process_output_item handles dict JSON correctly."""
        item_dict = {"type": "text", "text": '{"key": "value", "number": 42}'}

        result = component.process_output_item(item_dict)

        assert isinstance(result, dict)
        assert result == {"key": "value", "number": 42}

    def test_process_output_item_with_string_json(self, component):
        """Test that process_output_item wraps string JSON values in dict."""
        item_dict = {"type": "text", "text": '"hello world"'}

        result = component.process_output_item(item_dict)

        assert isinstance(result, dict)
        assert result["text"] == '"hello world"'
        assert result["parsed_value"] == "hello world"
        assert result["type"] == "text"

    def test_process_output_item_with_number_json(self, component):
        """Test that process_output_item wraps number JSON values in dict."""
        item_dict = {"type": "text", "text": "42"}

        result = component.process_output_item(item_dict)

        assert isinstance(result, dict)
        assert result["text"] == "42"
        assert result["parsed_value"] == 42
        assert result["type"] == "text"

    def test_process_output_item_with_array_json(self, component):
        """Test that process_output_item wraps array JSON values in dict."""
        item_dict = {"type": "text", "text": '["item1", "item2", "item3"]'}

        result = component.process_output_item(item_dict)

        assert isinstance(result, dict)
        assert result["text"] == '["item1", "item2", "item3"]'
        assert result["parsed_value"] == ["item1", "item2", "item3"]
        assert result["type"] == "text"

    def test_process_output_item_with_invalid_json(self, component):
        """Test that process_output_item handles invalid JSON gracefully."""
        item_dict = {"type": "text", "text": "not valid json {"}

        result = component.process_output_item(item_dict)

        assert isinstance(result, dict)
        assert result == item_dict

    def test_process_output_item_non_text_type(self, component):
        """Test that process_output_item returns non-text items unchanged."""
        item_dict = {"type": "image", "url": "https://example.com/image.png"}

        result = component.process_output_item(item_dict)

        assert result == item_dict

    @pytest.mark.asyncio
    async def test_build_output_creates_valid_dataframe(self, component):
        """Test that build_output creates a valid DataFrame with mixed JSON types."""
        # Setup component with mocked tools and cache
        component.tool = "test_tool"
        component.tools = []

        # Mock the tool cache
        mock_tool = MagicMock()
        mock_result = MagicMock()

        # Create mock output with various JSON types
        mock_content_item1 = MagicMock()
        mock_content_item1.model_dump.return_value = {"type": "text", "text": '{"status": "success"}'}

        mock_content_item2 = MagicMock()
        mock_content_item2.model_dump.return_value = {"type": "text", "text": '"just a string"'}

        mock_content_item3 = MagicMock()
        mock_content_item3.model_dump.return_value = {"type": "text", "text": "42"}

        mock_result.content = [mock_content_item1, mock_content_item2, mock_content_item3]
        mock_tool.coroutine = AsyncMock(return_value=mock_result)

        component._tool_cache = {"test_tool": mock_tool}

        # Mock update_tool_list
        component.update_tool_list = AsyncMock(return_value=([], None))

        # Mock get_inputs_for_all_tools to return empty list
        component.get_inputs_for_all_tools = MagicMock(return_value={"test_tool": []})

        # Execute build_output
        result = await component.build_output()

        # Verify result is a DataFrame
        assert isinstance(result, DataFrame)

        # Verify all items in DataFrame are dictionaries
        for _idx, row in result.iterrows():
            # Each row should be a valid Series (which can be converted to dict)
            assert row is not None

        # Verify the DataFrame has the expected number of rows
        assert len(result) == 3

        # Verify first row is the original dict
        assert result.iloc[0]["status"] == "success"

        # Verify second row is wrapped string
        assert result.iloc[1]["parsed_value"] == "just a string"
        assert result.iloc[1]["type"] == "text"

        # Verify third row is wrapped number
        assert result.iloc[2]["parsed_value"] == 42
        assert result.iloc[2]["type"] == "text"

    @pytest.mark.asyncio
    async def test_build_output_with_no_tool_selected(self, component):
        """Test that build_output returns error DataFrame when no tool is selected."""
        component.tool = ""
        component.update_tool_list = AsyncMock(return_value=([], None))

        result = await component.build_output()

        assert isinstance(result, DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["error"] == "You must select a tool"
