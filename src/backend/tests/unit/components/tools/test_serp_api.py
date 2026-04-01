from unittest.mock import MagicMock, patch

import pytest
from langchain_core.tools import ToolException
from langflow.custom import Component
from lfx.components.serpapi.serp import SerpComponent
from lfx.custom.utils import build_custom_component_template
from lfx.schema import Data
from lfx.schema.message import Message


def test_serpapi_initialization():
    component = SerpComponent()
    assert component.display_name == "Serp Search API"
    assert component.description == "Call Serp Search API with result limiting"
    assert component.icon == "SerpSearch"


def test_serpapi_template():
    serpapi = SerpComponent()
    component = Component(_code=serpapi._code)
    frontend_node, _ = build_custom_component_template(component)

    # Verify basic structure
    assert isinstance(frontend_node, dict)

    # Verify inputs
    assert "template" in frontend_node
    input_names = [input_["name"] for input_ in frontend_node["template"].values() if isinstance(input_, dict)]

    expected_inputs = ["serpapi_api_key", "input_value", "search_params", "max_results", "max_snippet_length"]

    for input_name in expected_inputs:
        assert input_name in input_names


@patch("lfx.components.serpapi.serp.SerpAPIWrapper")
def test_fetch_content(mock_serpapi_wrapper):
    component = SerpComponent()
    component.serpapi_api_key = "test-key"
    component.input_value = "test query"
    component.max_results = 3
    component.max_snippet_length = 100

    # Mock the SerpAPIWrapper and its results method
    mock_instance = MagicMock()
    mock_serpapi_wrapper.return_value = mock_instance
    mock_instance.results.return_value = {
        "organic_results": [
            {"title": "Test Result 1", "link": "https://test.com", "snippet": "This is a test result 1"},
            {"title": "Test Result 2", "link": "https://test2.com", "snippet": "This is a test result 2"},
        ]
    }

    result = component.fetch_content()

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0].text == "This is a test result 1"
    assert result[0].data["title"] == "Test Result 1"
    assert result[0].data["link"] == "https://test.com"


def test_fetch_content_text():
    component = SerpComponent()
    component.fetch_content = MagicMock(
        return_value=[
            Data(text="First result", data={"title": "Title 1"}),
            Data(text="Second result", data={"title": "Title 2"}),
        ]
    )

    result = component.fetch_content_text()

    assert isinstance(result, Message)
    assert result.text == "First result\nSecond result\n"


def test_error_handling():
    component = SerpComponent()
    component.serpapi_api_key = "test-key"
    component.input_value = "test query"

    with patch("lfx.components.serpapi.serp.SerpAPIWrapper") as mock_serpapi:
        mock_instance = MagicMock()
        mock_serpapi.return_value = mock_instance
        mock_instance.results.side_effect = Exception("API Error")

        with pytest.raises(ToolException):
            component.fetch_content()
