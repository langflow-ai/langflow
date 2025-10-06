import pytest
from lfx.components.processing.dataframe_to_toolset import DataFrameToToolsetComponent
from lfx.schema.dataframe import DataFrame


@pytest.fixture
def sample_dataframe():
    """Create sample data for testing."""
    sample_data = [
        {
            "action_name": "Get Weather Info",
            "content": "Current weather in San Francisco: Sunny, 72°F, Light breeze from the west.",
            "category": "weather",
        },
        {
            "action_name": "Check Stock Price",
            "content": "AAPL stock price: $190.25 (+2.5% today). Trading volume: 45.2M shares.",
            "category": "finance",
        },
        {
            "action_name": "Latest News",
            "content": (
                "Breaking: New AI breakthrough announced. Scientists develop more efficient language model "
                "architecture."
            ),
            "category": "news",
        },
        {
            "action_name": "Company Info",
            "content": (
                "Langflow: Open-source AI flow engineering platform for building LLM applications "
                "with visual interface."
            ),
            "category": "company",
        },
        {
            "action_name": "Get System Status",
            "content": "All systems operational. API response time: 45ms. Uptime: 99.9%",
            "category": "system",
        },
    ]
    return DataFrame(sample_data)


@pytest.fixture
def api_docs_dataframe():
    """Create API documentation DataFrame for testing."""
    api_docs_data = [
        {
            "endpoint": "POST /api/users",
            "description": "Creates a new user account with email and password",
            "example_response": '{"user_id": "12345", "email": "user@example.com", "status": "active"}',
            "status_code": "201",
        },
        {
            "endpoint": "GET /api/users/{id}",
            "description": "Retrieves user information by user ID",
            "example_response": '{"user_id": "12345", "email": "user@example.com", "created_at": "2024-01-15"}',
            "status_code": "200",
        },
        {
            "endpoint": "DELETE /api/users/{id}",
            "description": "Permanently deletes a user account",
            "example_response": '{"message": "User deleted successfully", "deleted_id": "12345"}',
            "status_code": "200",
        },
    ]
    return DataFrame(api_docs_data)


@pytest.fixture
def component():
    """Create a DataFrameToToolsetComponent instance."""
    return DataFrameToToolsetComponent()


class TestDataFrameToToolset:
    """Test the DataFrame to Toolset component with sample data."""

    def test_create_toolset_from_dataframe(self, component, sample_dataframe):
        """Test creating a toolset from a DataFrame."""
        # Set the inputs
        component.dataframe = sample_dataframe
        component.tool_name_column = "action_name"
        component.tool_output_column = "content"

        # Build the tools
        tools = component.build_tools()

        # Verify correct number of tools created
        assert len(tools) == 5, f"Expected 5 tools, got {len(tools)}"

        # Verify each tool has required attributes
        for tool in tools:
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")
            assert hasattr(tool, "metadata")
            assert hasattr(tool, "func")
            assert "display_name" in tool.metadata
            assert "content_preview" in tool.metadata

    def test_tool_metadata(self, component, sample_dataframe):
        """Test that tools have correct metadata."""
        component.dataframe = sample_dataframe
        component.tool_name_column = "action_name"
        component.tool_output_column = "content"

        tools = component.build_tools()

        # Check first tool metadata
        first_tool = tools[0]
        assert first_tool.metadata.get("display_name") == "Get Weather Info"
        assert "San Francisco" in first_tool.metadata.get("content_preview", "")

    def test_tool_execution(self, component, sample_dataframe):
        """Test executing tools returns correct content."""
        component.dataframe = sample_dataframe
        component.tool_name_column = "action_name"
        component.tool_output_column = "content"

        tools = component.build_tools()

        # Test first three tools
        expected_contents = [
            "Current weather in San Francisco: Sunny, 72°F, Light breeze from the west.",
            "AAPL stock price: $190.25 (+2.5% today). Trading volume: 45.2M shares.",
            "Breaking: New AI breakthrough announced. Scientists develop more efficient language model architecture.",
        ]

        for i, (tool, expected) in enumerate(zip(tools[:3], expected_contents, strict=False)):
            result = tool.func()
            assert result == expected, f"Tool {i} returned unexpected content"

    def test_component_message_output(self, component, sample_dataframe):
        """Test the message output from the component."""
        component.dataframe = sample_dataframe
        component.tool_name_column = "action_name"
        component.tool_output_column = "content"

        # Build tools first
        component.build_tools()

        # Get message output
        message = component.get_message()

        assert message is not None
        assert hasattr(message, "text")
        assert len(message.text) > 0

    def test_component_data_output(self, component, sample_dataframe):
        """Test the data output from the component."""
        component.dataframe = sample_dataframe
        component.tool_name_column = "action_name"
        component.tool_output_column = "content"

        # Build tools first
        component.build_tools()

        # Get data output
        data_results = component.run_model()

        assert len(data_results) > 0
        for data in data_results:
            assert hasattr(data, "data")


class TestDifferentColumnCombinations:
    """Test with different column combinations to show flexibility."""

    def test_api_documentation_columns(self, component, api_docs_dataframe):
        """Test using endpoint as action name and description as content."""
        # Use endpoint as action name and description as content
        component.dataframe = api_docs_dataframe
        component.tool_name_column = "endpoint"
        component.tool_output_column = "description"

        tools = component.build_tools()

        assert len(tools) == 3, f"Expected 3 tools, got {len(tools)}"

        # Verify endpoints are used as display names
        display_names = [tool.metadata.get("display_name") for tool in tools]
        assert "POST /api/users" in display_names
        assert "GET /api/users/{id}" in display_names
        assert "DELETE /api/users/{id}" in display_names

    def test_api_tool_content(self, component, api_docs_dataframe):
        """Test that API tools return correct descriptions."""
        component.dataframe = api_docs_dataframe
        component.tool_name_column = "endpoint"
        component.tool_output_column = "description"

        tools = component.build_tools()

        # Test first tool
        first_tool = tools[0]
        result = first_tool.func()
        assert "Creates a new user account" in result


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_dataframe(self, component):
        """Test with an empty DataFrame."""
        empty_df = DataFrame([])
        component.dataframe = empty_df
        component.tool_name_column = "action_name"
        component.tool_output_column = "content"

        # Expect an error here
        with pytest.raises(ValueError, match=r"Tool name column 'action_name' not found in DataFrame columns: \[\]"):
            component.build_tools()

    def test_missing_column(self, component, sample_dataframe):
        """Test with non-existent column names."""
        component.dataframe = sample_dataframe
        component.tool_name_column = "non_existent_column"
        component.tool_output_column = "content"

        with pytest.raises(
            ValueError, match=r"Tool name column 'non_existent_column' not found in DataFrame columns: .*"
        ):
            component.build_tools()

    def test_single_row_dataframe(self, component):
        """Test with a DataFrame containing only one row."""
        single_row_data = [
            {
                "action_name": "Single Action",
                "content": "This is the only content",
            }
        ]
        df = DataFrame(single_row_data)

        component.dataframe = df
        component.tool_name_column = "action_name"
        component.tool_output_column = "content"

        tools = component.build_tools()

        assert len(tools) == 1
        assert tools[0].metadata.get("display_name") == "Single Action"
        assert tools[0].func() == "This is the only content"


class TestToolNaming:
    """Test tool naming conventions."""

    def test_tool_names_are_sanitized(self, component):
        """Test that tool names are properly sanitized for function names."""
        data = [
            {
                "action_name": "Get Weather Info!",
                "content": "Weather data",
            },
            {
                "action_name": "Check Stock Price?",
                "content": "Stock data",
            },
        ]
        df = DataFrame(data)

        component.dataframe = df
        component.tool_name_column = "action_name"
        component.tool_output_column = "content"

        tools = component.build_tools()

        # Tool names should be valid Python identifiers
        for tool in tools:
            assert tool.name.isidentifier() or "_" in tool.name


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
