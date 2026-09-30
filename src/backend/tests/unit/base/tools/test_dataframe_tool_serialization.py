"""Test DataFrame serialization in tool mode."""

import pandas as pd
import pytest
from lfx.base.tools.component_tool import ComponentToolkit
from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.dataframe import DataFrame, Table


class DataFrameComponent(Component):
    """Test component that returns a DataFrame."""

    display_name = "DataFrame Test Component"
    description = "Returns a DataFrame for testing tool serialization"
    icon = "test"
    name = "DataFrameTest"

    inputs = [
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(
            name="get_data",
            display_name="Data",
            method="get_data",
        ),
    ]

    def get_data(self) -> DataFrame:
        """Return a DataFrame with content that would be truncated by pandas default repr."""
        # Create data with long content to trigger truncation if using pandas repr
        long_content = (
            "This is a very long piece of content that would be truncated to 50 "
            "characters by pandas default display settings"
        )
        data = [
            {
                "id": "1",
                "content": long_content,
                "score": 0.95,
            },
            {
                "id": "2",
                "content": long_content,
                "score": 0.87,
            },
        ]
        # Convert to DataFrame then back to our DataFrame schema
        df = pd.DataFrame(data)
        return DataFrame(
            data=[{"id": row["id"], "content": row["content"], "score": row["score"]} for _, row in df.iterrows()]
        )


def test_dataframe_tool_serialization():
    """Test that DataFrame tool results stringify without pandas column-width truncation."""
    component = DataFrameComponent()
    component_toolkit = ComponentToolkit(component=component)
    tool = component_toolkit.get_tools()[0]

    # Invoke the tool
    result = tool.invoke(input={"search_query": "test query"})

    # Tool returns the Table (pandas DataFrame subclass); LangChain stringifies it for
    # the agent observation. The fix ensures __repr__/__str__ disable max_colwidth
    # truncation so the full content reaches the agent.
    assert isinstance(result, Table), f"Expected Table, got {type(result)}"
    assert len(result) == 2

    # Force a wide pandas display so column-dropping from terminal width doesn't
    # interfere with what we're actually testing: max_colwidth truncation.
    with pd.option_context("display.width", 10_000, "display.max_columns", None):
        rendered = str(result)

    # Full content must survive stringification (pandas default truncates cells at 50 chars).
    assert "This is a very long piece of content that would be truncated" in rendered
    assert "characters by pandas default display settings" in rendered
    # Pandas inserts "..." as the column-width truncation marker; it must not appear.
    assert "..." not in rendered


def test_dataframe_tool_result_format():
    """Test that DataFrame tool results preserve all rows and columns."""
    component = DataFrameComponent()
    component_toolkit = ComponentToolkit(component=component)
    tool = component_toolkit.get_tools()[0]

    result = tool.invoke(input={"search_query": "test"})

    # Verify structure: a Table with the expected rows/columns
    assert isinstance(result, Table)
    assert list(result.columns) == ["id", "content", "score"]
    assert len(result) == 2

    # to_dict gives the canonical list-of-dicts view; verify keys per row
    expected_keys = {"id", "content", "score"}
    for row in result.to_dict(orient="records"):
        assert set(row.keys()) == expected_keys


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
