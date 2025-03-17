from unittest.mock import AsyncMock

import pytest

from langflow.components import processing
from langflow.schema import Data


@pytest.fixture
def lambda_filter():
    # This fixture provides an instance of LambdaFilter for each test case
    return processing.LambdaFilterComponent()


async def test_successful_lambda_generation(lambda_filter):
    # Mock data and LLM response
    test_data = {"items": [{"name": "test1", "value": 10}, {"name": "test2", "value": 20}]}
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value.content = "lambda x: [item for item in x['items'] if item['value'] > 15]"

    # Configure component
    lambda_filter.set_attributes(
        {
            "data": [Data(data=test_data)],
            "llm": mock_llm,
            "filter_instruction": "Filter items with value greater than 15",
            "sample_size": 1000,
        }
    )

    # Execute filter
    result = await lambda_filter.filter_data()

    # Assertions
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].name == "test2"
    assert result[0].value == 20


async def test_invalid_lambda_response(lambda_filter):
    # Mock data and invalid LLM response
    test_data = {"items": [{"name": "test1", "value": 10}]}
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value.content = "invalid lambda syntax"

    # Configure component
    lambda_filter.set_attributes(
        {"data": [Data(data=test_data)], "llm": mock_llm, "filter_instruction": "Filter items", "sample_size": 1000}
    )

    # Test exception handling
    with pytest.raises(ValueError, match="Could not find lambda in response"):
        await lambda_filter.filter_data()


async def test_lambda_with_large_dataset(lambda_filter):
    # Create a large dataset
    large_data = {"items": [{"name": f"test{i}", "value": i} for i in range(2000)]}
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value.content = "lambda x: [item for item in x['items'] if item['value'] > 1500]"

    # Configure component
    lambda_filter.set_attributes(
        {
            "data": [Data(data=large_data)],
            "llm": mock_llm,
            "filter_instruction": "Filter items with value greater than 1500",
            "sample_size": 100,
        }
    )

    # Execute filter
    result = await lambda_filter.filter_data()

    # Assertions
    assert isinstance(result, list)
    assert len(result) == 499  # Items with value from 1501 to 1999
    assert all(item.value > 1500 for item in result)


async def test_lambda_with_complex_data_structure(lambda_filter):
    # Test with nested data structure
    complex_data = {
        "categories": {
            "A": [{"id": 1, "score": 90}, {"id": 2, "score": 85}],
            "B": [{"id": 3, "score": 95}, {"id": 4, "score": 88}],
        }
    }
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value.content = (
        "lambda x: [item for cat in x['categories'].values() for item in cat if item['score'] > 90]"
    )

    # Configure component
    lambda_filter.set_attributes(
        {
            "data": [Data(data=complex_data)],
            "llm": mock_llm,
            "filter_instruction": "Filter items with score greater than 90",
            "sample_size": 1000,
        }
    )

    # Execute filter
    result = await lambda_filter.filter_data()

    # Assertions
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].id == 3
    assert result[0].score == 95


def test_get_data_structure(lambda_filter):
    # Test the data structure extraction
    test_data = {
        "string": "test",
        "number": 42,
        "list": [1, 2, 3],
        "dict": {"key": "value"},
        "nested": {"a": [{"b": 1}]},
    }

    structure = lambda_filter.get_data_structure(test_data)

    # Assertions
    assert structure["string"]["structure"] == "str"
    assert structure["number"]["structure"] == "int"
    assert structure["list"]["structure"] == "list(int)[size=3]"
    assert structure["dict"]["structure"]["key"] == "str"
    assert "structure" in structure["nested"]
    assert "a" in structure["nested"]["structure"]
    assert "list" in structure["nested"]["structure"]["a"]
