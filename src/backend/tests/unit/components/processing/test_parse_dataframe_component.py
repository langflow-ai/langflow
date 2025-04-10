import asyncio

import pandas as pd
import pytest
from langflow.components.processing.parse_dataframe import ParseDataFrameComponent
from langflow.schema import DataFrame
from langflow.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


class TestParseDataFrameComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return ParseDataFrameComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {"df": DataFrame({"text": ["Hello"]}), "template": "{text}", "sep": "\n"}

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    def test_successful_parse_with_default_template(self):
        # Create test data
        test_df = DataFrame({"text": ["Hello", "World", "Test"]})

        component = ParseDataFrameComponent(df=test_df, template="{text}", sep="\n")

        # Run the parse process
        result = component.parse_data()

        # Verify the results
        assert isinstance(result, Message)
        assert result.text == "Hello\nWorld\nTest"
        assert component.status == "Hello\nWorld\nTest"

    def test_parse_with_custom_template(self):
        test_df = DataFrame({"name": ["John", "Jane"], "age": [30, 25]})

        component = ParseDataFrameComponent(df=test_df, template="Name: {name}, Age: {age}", sep=" | ")

        result = component.parse_data()

        assert isinstance(result, Message)
        assert result.text == "Name: John, Age: 30 | Name: Jane, Age: 25"

    def test_parse_with_custom_separator(self):
        test_df = DataFrame({"text": ["Hello", "World"]})

        component = ParseDataFrameComponent(df=test_df, template="{text}", sep=" --- ")

        result = component.parse_data()

        assert isinstance(result, Message)
        assert result.text == "Hello --- World"

    def test_empty_dataframe(self):
        component = ParseDataFrameComponent(df=DataFrame({"text": []}), template="{text}", sep="\n")

        result = component.parse_data()
        assert isinstance(result, Message)
        assert result.text == ""

    def test_invalid_template_keys(self):
        component = ParseDataFrameComponent(
            df=DataFrame({"text": ["Hello"]}), template="{nonexistent_column}", sep="\n"
        )

        with pytest.raises(KeyError):
            component.parse_data()

    def test_multiple_column_template(self):
        test_df = DataFrame({"col1": ["A", "B"], "col2": [1, 2], "col3": ["X", "Y"]})

        component = ParseDataFrameComponent(df=test_df, template="{col1}-{col2}-{col3}", sep=", ")

        result = component.parse_data()
        assert isinstance(result, Message)
        assert result.text == "A-1-X, B-2-Y"

    @pytest.mark.asyncio
    async def test_async_invocation(self, component_class, default_kwargs):
        """Verify that ParseDataFrameComponent can be called in an async context."""
        component = component_class(**default_kwargs)
        # Use asyncio.to_thread to invoke the parse_data method in a thread pool
        result = await asyncio.to_thread(component.parse_data)
        assert isinstance(result, Message)

    def test_various_data_types(self, component_class):
        """Test that the component correctly formats differing data types."""
        test_dataframe = DataFrame(
            {
                "string_col": ["A", "B"],
                "int_col": [1, 2],
                "bool_col": [True, False],
                "time_col": pd.to_datetime(["2023-01-01", "2023-01-02"]),
            }
        )
        template = "{string_col}-{int_col}-{bool_col}-{time_col}"
        component = component_class(df=test_dataframe, template=template, sep=" | ")
        result = component.parse_data()
        assert isinstance(result, Message)
        # Just check that all columns are present in the text
        assert "A-1-True-2023-01-01" in result.text

    def test_nan_values(self, component_class):
        """Test how the component handles missing/NaN values in the DataFrame."""
        test_dataframe = DataFrame(
            {
                "col1": ["Hello", None],
                "col2": [10, float("nan")],
            }
        )
        template = "{col1}-{col2}"
        component = component_class(df=test_dataframe, template=template, sep="\n")
        result = component.parse_data()
        # Expect None or NaN to be converted to the string "None" or "nan"
        # depending on Python's behavior
        assert isinstance(result, Message)
        # The exact representation can depend on how pandas handles None/NaN.
        # Typically, None -> 'None' and NaN -> 'nan'.
        # You can refine these assertions if you have a custom conversion.
        assert "Hello-10" in result.text

    def test_large_dataframe(self, component_class):
        """Test performance and correctness on a relatively large DataFrame."""
        data = {
            "col": [f"Row{i}" for i in range(10000)],  # 10k rows
        }
        large_dataframe = DataFrame(data)
        component = component_class(df=large_dataframe, template="{col}", sep=", ")
        result = component.parse_data()
        assert isinstance(result, Message)
        # Check the length of the result isn't zero, ensuring it didn't fail
        assert len(result.text) > 0
        # Optionally, you can assert the result includes a substring from the middle
        assert "Row5000" in result.text
