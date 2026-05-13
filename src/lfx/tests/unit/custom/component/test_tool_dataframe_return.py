"""Test that component tools returning DataFrames pass them through without serialization.

When a component output method returns a pandas DataFrame, the tool wrapper
must return the DataFrame directly (not serialize it to a list of dicts).
This allows agents like OpenDsStar to use the DataFrame natively with
.shape, .columns, pd operations, etc.
"""

import pandas as pd
import pytest
from lfx.base.tools.component_tool import ComponentToolkit
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.io import Output
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message


class DataFrameProducerComponent(Component):
    """Test component that returns a DataFrame from its output method."""

    display_name = "DataFrame Producer"
    description = "Returns a DataFrame for testing."
    name = "DataFrameProducerComponent"

    inputs = [
        MessageTextInput(name="query", display_name="Query", tool_mode=True),
    ]

    outputs = [
        Output(display_name="Table", name="table", method="get_table"),
        Output(display_name="Text", name="text", method="get_text"),
    ]

    def get_table(self) -> DataFrame:
        df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
        return DataFrame(df)

    def get_text(self) -> Message:
        return Message(text=f"query was: {self.query}")


class AsyncTextComponent(Component):
    """Test component with an async output method."""

    display_name = "Async Text"
    description = "Returns text asynchronously."
    name = "AsyncTextComponent"

    inputs = [
        MessageTextInput(name="query", display_name="Query", tool_mode=True),
    ]

    outputs = [
        Output(display_name="Text", name="text", method="get_text"),
    ]

    async def get_text(self) -> Message:
        return Message(text=f"async query was: {self.query}")


def test_tool_returns_dataframe_not_list():
    """Tool wrapping a DataFrame output must return a DataFrame, not a serialized list."""
    component = DataFrameProducerComponent()
    toolkit = ComponentToolkit(component=component)
    tools = toolkit.get_tools()

    # Find the table tool
    table_tool = next(t for t in tools if t.name == "get_table")

    result = table_tool.invoke({"query": "test"})

    assert isinstance(result, pd.DataFrame), f"Expected pandas DataFrame, got {type(result).__name__}: {result!r}"
    assert list(result.columns) == ["col1", "col2"]
    assert len(result) == 3
    assert result["col1"].tolist() == [1, 2, 3]


def test_tool_returns_text_for_message():
    """Tool wrapping a Message output must still return text (not change behavior)."""
    component = DataFrameProducerComponent()
    toolkit = ComponentToolkit(component=component)
    tools = toolkit.get_tools()

    text_tool = next(t for t in tools if t.name == "get_text")

    result = text_tool.invoke({"query": "hello"})

    assert isinstance(result, str)
    assert "hello" in result


def test_dataframe_is_picklable():
    """DataFrame returned by tool must be picklable for cross-process transfer."""
    import pickle

    component = DataFrameProducerComponent()
    toolkit = ComponentToolkit(component=component)
    tools = toolkit.get_tools()

    table_tool = next(t for t in tools if t.name == "get_table")
    result = table_tool.invoke({"query": "test"})

    # Must be picklable for multiprocessing pipe
    pickled = pickle.dumps(result)
    restored = pickle.loads(pickled)  # noqa: S301

    assert isinstance(restored, pd.DataFrame)
    assert list(restored.columns) == ["col1", "col2"]
    assert len(restored) == 3


def test_tool_handles_positional_args():
    """Tool must accept positional args by mapping them to tool_mode input names."""
    component = DataFrameProducerComponent()
    toolkit = ComponentToolkit(component=component)
    tools = toolkit.get_tools()

    text_tool = next(t for t in tools if t.name == "get_text")

    # Invoke with positional arg (as OpenDsStar's generated code does)
    result = text_tool.func("my_query")

    assert isinstance(result, str)
    assert "my_query" in result


@pytest.mark.asyncio
async def test_tool_handles_positional_args_async():
    """Async tool must accept positional args by mapping them to tool_mode input names."""
    component = AsyncTextComponent()
    toolkit = ComponentToolkit(component=component)
    tools = toolkit.get_tools()

    text_tool = next(t for t in tools if t.name == "get_text")

    # Invoke the async coroutine with a positional arg
    result = await text_tool.coroutine("my_async_query")

    assert isinstance(result, str)
    assert "my_async_query" in result
