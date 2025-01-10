from unittest.mock import patch

import pytest
from langflow.components.tools import GoogleSearchAPIComponent
from langflow.schema import DataFrame


@pytest.fixture
def google_search_component():
    return GoogleSearchAPIComponent()


@pytest.fixture
def mock_search_results():
    return [
        {
            "title": "Test Title 1",
            "link": "https://test1.com",
            "snippet": "Test snippet 1",
        },
        {
            "title": "Test Title 2",
            "link": "https://test2.com",
            "snippet": "Test snippet 2",
        },
    ]


def test_component_initialization(google_search_component):
    # Test basic component attributes
    assert google_search_component.display_name == "Google Search API"
    assert google_search_component.icon == "Google"

    # Test inputs configuration
    input_names = [input_.name for input_ in google_search_component.inputs]
    assert "google_api_key" in input_names
    assert "google_cse_id" in input_names
    assert "input_value" in input_names
    assert "k" in input_names

    # Test outputs configuration
    output_names = [output.name for output in google_search_component.outputs]
    assert "results" in output_names


@patch("langchain_google_community.GoogleSearchAPIWrapper.results")
def test_search_google_success(mock_results, google_search_component, mock_search_results):
    # Configure component
    google_search_component.google_api_key = "test_api_key"
    google_search_component.google_cse_id = "test_cse_id"
    google_search_component.input_value = "test query"
    google_search_component.k = 2

    # Configure mock
    mock_results.return_value = mock_search_results

    # Execute search
    result = google_search_component.search_google()

    # Verify results
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["title"] == "Test Title 1"
    assert result[1]["link"] == "https://test2.com"

    # Verify mock calls
    mock_results.assert_called_once_with(query="test query", num_results=2)


def test_search_google_invalid_api_key(google_search_component):
    # Test with invalid API key
    google_search_component.google_api_key = "from langflow.io import Output"
    result = google_search_component.search_google()

    assert isinstance(result, DataFrame)
    assert "error" in result.columns
    assert "Invalid Google API Key" in result.iloc[0]["error"]


def test_search_google_invalid_cse_id(google_search_component):
    # Test with valid API key but invalid CSE ID
    google_search_component.google_api_key = "valid_key"
    google_search_component.google_cse_id = "from langflow.io import Output"
    result = google_search_component.search_google()

    assert isinstance(result, DataFrame)
    assert "error" in result.columns
    assert "Invalid Google CSE ID" in result.iloc[0]["error"]


@patch("langchain_google_community.GoogleSearchAPIWrapper.results")
def test_search_google_error_handling(mock_results, google_search_component):
    # Configure component
    google_search_component.google_api_key = "test_api_key"
    google_search_component.google_cse_id = "test_cse_id"
    google_search_component.input_value = "test query"
    google_search_component.k = 2

    # Configure mock to raise an error
    mock_results.side_effect = ConnectionError("API connection failed")

    # Execute search
    result = google_search_component.search_google()

    # Verify error handling
    assert isinstance(result, DataFrame)
    assert "error" in result.columns
    assert "API connection failed" in result.iloc[0]["error"]


def test_build_method(google_search_component):
    # Test build method returns the correct function
    build_result = google_search_component.build()
    assert build_result == google_search_component.search_google
