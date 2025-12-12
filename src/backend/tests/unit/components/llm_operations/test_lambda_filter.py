from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.components.llm_operations.lambda_filter import LambdaFilterComponent
from lfx.schema import Data

from tests.base import ComponentTestBaseWithoutClient


class TestLambdaFilterComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return LambdaFilterComponent

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM that works with async invoke."""
        mock = AsyncMock()
        mock.ainvoke = AsyncMock()
        return mock

    @pytest.fixture
    def model_metadata(self):
        """Helper fixture that returns standard model metadata structure."""
        return [
            {
                "name": "gpt-3.5-turbo",
                "provider": "OpenAI",
                "metadata": {
                    "model_class": "MockLanguageModel",
                    "model_name_param": "model",
                    "api_key_param": "api_key",
                },
            }
        ]

    @pytest.fixture
    def default_kwargs(self, model_metadata):
        """Return the default kwargs for the component with proper model metadata."""
        return {
            "data": [Data(data={"items": [{"name": "test1", "value": 10}, {"name": "test2", "value": 20}]})],
            "model": model_metadata,
            "api_key": "test-api-key",
            "filter_instruction": "Filter items with value greater than 15",
            "sample_size": 1000,
            "max_size": 30000,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    @patch("lfx.base.models.unified_models.get_model_classes")
    async def test_invalid_lambda_response(self, mock_get_model_classes, component_class, default_kwargs, mock_llm):
        # Mock get_model_classes to return MockLanguageModel factory
        mock_model_class = MagicMock(return_value=mock_llm)
        mock_get_model_classes.return_value = {"MockLanguageModel": mock_model_class}

        component = await self.component_setup(component_class, default_kwargs)
        mock_llm.ainvoke.return_value.content = "invalid lambda syntax"

        # Test exception handling
        with pytest.raises(ValueError, match="Could not find lambda in response"):
            await component.process_as_data()

    @patch("lfx.base.models.unified_models.get_model_classes")
    async def test_successful_lambda_generation(
        self, mock_get_model_classes, component_class, default_kwargs, mock_llm
    ):
        """Test that a lambda function is successfully generated and applied."""
        # Mock get_model_classes to return MockLanguageModel factory
        mock_model_class = MagicMock(return_value=mock_llm)
        mock_get_model_classes.return_value = {"MockLanguageModel": mock_model_class}

        component = await self.component_setup(component_class, default_kwargs)
        mock_llm.ainvoke.return_value.content = "lambda x: [item for item in x['items'] if item['value'] > 15]"

        # Execute the lambda filter
        result = await component.process_as_data()

        # Assertions - process_as_data() returns a Data object
        assert isinstance(result, Data), f"Expected Data object, got {type(result)}"
        assert "_results" in result.data, "Expected '_results' key in Data object"

        # Check the filtered results
        filtered_items = result.data["_results"]
        assert isinstance(filtered_items, list), "Expected list of filtered items"
        assert len(filtered_items) == 1, f"Expected 1 item, got {len(filtered_items)}"
        assert filtered_items[0]["name"] == "test2", f"Expected 'test2', got {filtered_items[0]['name']}"
        assert filtered_items[0]["value"] == 20, f"Expected value 20, got {filtered_items[0]['value']}"

    @patch("lfx.base.models.unified_models.get_model_classes")
    async def test_lambda_with_large_dataset(self, mock_get_model_classes, component_class, default_kwargs, mock_llm):
        """Test lambda execution with a large dataset."""
        # Mock get_model_classes to return MockLanguageModel factory
        mock_model_class = MagicMock(return_value=mock_llm)
        mock_get_model_classes.return_value = {"MockLanguageModel": mock_model_class}

        large_data = {"items": [{"name": f"test{i}", "value": i} for i in range(2000)]}
        default_kwargs["data"] = [Data(data=large_data)]
        default_kwargs["filter_instruction"] = "Filter items with value greater than 1500"
        component = await self.component_setup(component_class, default_kwargs)
        mock_llm.ainvoke.return_value.content = "lambda x: [item for item in x['items'] if item['value'] > 1500]"

        # Execute filter on the data
        result = await component.process_as_data()

        # Assertions - process_as_data() returns a Data object
        assert isinstance(result, Data), f"Expected Data object, got {type(result)}"
        assert "_results" in result.data, "Expected '_results' key in Data object"

        # Check the filtered results from the lambda
        filtered_items = result.data["_results"]
        assert isinstance(filtered_items, list), "Expected list of filtered items"
        assert len(filtered_items) == 499, f"Expected 499 items (1501-1999), got {len(filtered_items)}"

        # Verify first and last items
        assert filtered_items[0]["value"] == 1501, f"Expected first value 1501, got {filtered_items[0]['value']}"
        assert filtered_items[-1]["value"] == 1999, f"Expected last value 1999, got {filtered_items[-1]['value']}"

    @patch("lfx.base.models.unified_models.get_model_classes")
    async def test_lambda_with_complex_data_structure(
        self, mock_get_model_classes, component_class, default_kwargs, mock_llm
    ):
        """Test lambda execution with complex nested data structures."""
        # Mock get_model_classes to return MockLanguageModel factory
        mock_model_class = MagicMock(return_value=mock_llm)
        mock_get_model_classes.return_value = {"MockLanguageModel": mock_model_class}

        complex_data = {
            "categories": {
                "A": [{"id": 1, "score": 90}, {"id": 2, "score": 85}],
                "B": [{"id": 3, "score": 95}, {"id": 4, "score": 88}],
            }
        }
        default_kwargs["data"] = [Data(data=complex_data)]
        default_kwargs["filter_instruction"] = "Filter items with score greater than 90"
        component = await self.component_setup(component_class, default_kwargs)
        mock_llm.ainvoke.return_value.content = (
            "lambda x: [item for cat in x['categories'].values() for item in cat if item['score'] > 90]"
        )

        # Execute filter
        result = await component.process_as_data()

        # Assertions - process_as_data() returns a Data object
        assert isinstance(result, Data), f"Expected Data object, got {type(result)}"
        assert "_results" in result.data, "Expected '_results' key in Data object"

        # Check the filtered results
        filtered_items = result.data["_results"]
        assert isinstance(filtered_items, list), "Expected list of filtered items"
        assert len(filtered_items) == 1, f"Expected 1 item with score > 90, got {len(filtered_items)}"
        assert filtered_items[0]["id"] == 3, f"Expected id 3, got {filtered_items[0]['id']}"
        assert filtered_items[0]["score"] == 95, f"Expected score 95, got {filtered_items[0]['score']}"

    def test_validate_lambda(self, component_class):
        component = component_class()

        # Valid lambda
        valid_lambda = "lambda x: x + 1"
        assert component._validate_lambda(valid_lambda) is True

        # Invalid lambda: missing 'lambda'
        invalid_lambda_1 = "x: x + 1"
        assert component._validate_lambda(invalid_lambda_1) is False

        # Invalid lambda: missing ':'
        invalid_lambda_2 = "lambda x x + 1"
        assert component._validate_lambda(invalid_lambda_2) is False

    def test_get_data_structure(self, component_class):
        """Test that get_data_structure returns a mirror of the data with types."""
        component = component_class()
        test_data = {
            "string": "test",
            "number": 42,
            "list": [1, 2, 3],
            "dict": {"key": "value"},
            "nested": {"a": [{"b": 1}]},
        }

        structure = component.get_data_structure(test_data)

        # Verify the structure returns type names for primitive types
        assert structure["string"] == "str", f"Expected 'str', got {structure['string']}"
        assert structure["number"] == "int", f"Expected 'int', got {structure['number']}"

        # Verify list structure
        assert isinstance(structure["list"], list), "List should return a list structure"
        assert structure["list"] == ["int"], f"Expected ['int'], got {structure['list']}"

        # Verify dict structure
        assert isinstance(structure["dict"], dict), "Dict should return a dict structure"
        assert structure["dict"] == {"key": "str"}, f"Expected {{'key': 'str'}}, got {structure['dict']}"

        # Verify nested structure
        assert structure["nested"] == {"a": [{"b": "int"}]}, (
            f"Expected nested structure {{'a': [{{'b': 'int'}}]}}, got {structure['nested']}"
        )
