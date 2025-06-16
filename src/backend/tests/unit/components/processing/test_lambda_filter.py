from unittest.mock import AsyncMock

import pytest
from langflow.components.processing.smart_function import SmartFunctionComponent
from langflow.schema import Data

from tests.base import ComponentTestBaseWithoutClient


class TestLambdaFilterComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return SmartFunctionComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "data": [Data(data={"items": [{"name": "test1", "value": 10}, {"name": "test2", "value": 20}]})],
            "llm": AsyncMock(),
            "filter_instruction": "Filter items with value greater than 15",
            "sample_size": 1000,
            "max_size": 30000,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def test_successful_lambda_generation(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        component.llm.ainvoke.return_value.content = "lambda x: [item for item in x['items'] if item['value'] > 15]"

        # Execute filter
        result = await component.filter_data()

        # Assertions
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].name == "test2"
        assert result[0].value == 20

    async def test_invalid_lambda_response(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        component.llm.ainvoke.return_value.content = "invalid lambda syntax"

        # Test exception handling
        with pytest.raises(ValueError, match="Could not find lambda in response"):
            await component.filter_data()

    async def test_lambda_with_large_dataset(self, component_class, default_kwargs):
        large_data = {"items": [{"name": f"test{i}", "value": i} for i in range(2000)]}
        default_kwargs["data"] = [Data(data=large_data)]
        default_kwargs["filter_instruction"] = "Filter items with value greater than 1500"
        component = await self.component_setup(component_class, default_kwargs)
        component.llm.ainvoke.return_value.content = "lambda x: [item for item in x['items'] if item['value'] > 1500]"

        # Execute filter
        result = await component.filter_data()

        # Assertions
        assert isinstance(result, list)
        assert len(result) == 499  # Items with value from 1501 to 1999
        assert all(item.value > 1500 for item in result)

    async def test_lambda_with_complex_data_structure(self, component_class, default_kwargs):
        complex_data = {
            "categories": {
                "A": [{"id": 1, "score": 90}, {"id": 2, "score": 85}],
                "B": [{"id": 3, "score": 95}, {"id": 4, "score": 88}],
            }
        }
        default_kwargs["data"] = [Data(data=complex_data)]
        default_kwargs["filter_instruction"] = "Filter items with score greater than 90"
        component = await self.component_setup(component_class, default_kwargs)
        component.llm.ainvoke.return_value.content = (
            "lambda x: [item for cat in x['categories'].values() for item in cat if item['score'] > 90]"
        )

        # Execute filter
        result = await component.filter_data()

        # Assertions
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].id == 3
        assert result[0].score == 95

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
        component = component_class()
        test_data = {
            "string": "test",
            "number": 42,
            "list": [1, 2, 3],
            "dict": {"key": "value"},
            "nested": {"a": [{"b": 1}]},
        }

        structure = component.get_data_structure(test_data)

        # Assertions
        assert structure["string"]["structure"] == "str"
        assert structure["number"]["structure"] == "int"
        assert structure["list"]["structure"] == "list(int)[size=3]"
        assert structure["dict"]["structure"]["key"] == "str"
        assert "structure" in structure["nested"]
        assert "a" in structure["nested"]["structure"]
        assert "list" in structure["nested"]["structure"]["a"]
