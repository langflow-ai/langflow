import re

import pytest
from langflow.components.helpers.batch_run import BatchRunComponent
from langflow.schema import DataFrame

from tests.base import ComponentTestBaseWithoutClient
from tests.unit.mock_language_model import MockLanguageModel


class TestBatchRunComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return BatchRunComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "model": MockLanguageModel(),
            "df": DataFrame({"text": ["Hello"]}),
            "column_name": "text",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    async def test_successful_batch_run_with_system_message(self):
        # Create test data
        test_df = DataFrame({"text": ["Hello", "World", "Test"]})

        component = BatchRunComponent(
            model=MockLanguageModel(), system_message="You are a helpful assistant", df=test_df, column_name="text"
        )

        # Run the batch process
        result = await component.run_batch()

        # Verify the results
        assert isinstance(result, DataFrame)
        assert "text_input" in result.columns
        assert "model_response" in result.columns
        assert len(result) == 3
        assert all(isinstance(resp, str) for resp in result["model_response"])

    async def test_batch_run_without_system_message(self):
        test_df = DataFrame({"text": ["Hello", "World"]})

        component = BatchRunComponent(model=MockLanguageModel(), df=test_df, column_name="text")

        result = await component.run_batch()

        assert isinstance(result, DataFrame)
        assert len(result) == 2
        assert all(isinstance(resp, str) for resp in result["model_response"])

    async def test_invalid_column_name(self):
        component = BatchRunComponent(
            model=MockLanguageModel(), df=DataFrame({"text": ["Hello"]}), column_name="nonexistent_column"
        )

        with pytest.raises(ValueError, match=re.escape("Column 'nonexistent_column' not found in the DataFrame.")):
            await component.run_batch()

    async def test_empty_dataframe(self):
        component = BatchRunComponent(model=MockLanguageModel(), df=DataFrame({"text": []}), column_name="text")

        result = await component.run_batch()
        assert isinstance(result, DataFrame)
        assert len(result) == 0

    async def test_non_string_column_conversion(self):
        test_df = DataFrame(
            {
                "text": [123, 456, 789]  # Numeric values
            }
        )

        component = BatchRunComponent(model=MockLanguageModel(), df=test_df, column_name="text")

        result = await component.run_batch()

        assert isinstance(result, DataFrame)
        assert all(isinstance(text, str) for text in result["text_input"])
        assert all(str(num) in text for num, text in zip(test_df["text"], result["text_input"], strict=False))
