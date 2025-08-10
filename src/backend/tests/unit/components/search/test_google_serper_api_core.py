from unittest.mock import MagicMock, patch

import pytest
from langflow.components.google.google_serper_api_core import GoogleSerperAPICore
from langflow.schema import DataFrame


@pytest.fixture
def google_serper_component():
    return GoogleSerperAPICore()


@pytest.fixture
def mock_search_results():
    return {
        "organic": [
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
    }


def test_component_initialization(google_serper_component):
    assert google_serper_component.display_name == "Google Serper API"
    assert google_serper_component.icon == "Serper"

    input_names = [input_.name for input_ in google_serper_component.inputs]
    assert "serper_api_key" in input_names
    assert "input_value" in input_names
    assert "k" in input_names


@patch("langchain_community.utilities.google_serper.requests.get")
@patch("langchain_community.utilities.google_serper.requests.post")
def test_search_serper_success(mock_post, mock_get, google_serper_component, mock_search_results):
    # Configure mocks
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_search_results
    mock_post.return_value = mock_response
    mock_get.return_value = mock_response

    # Configure component
    google_serper_component.serper_api_key = "test_api_key"
    google_serper_component.input_value = "test query"
    google_serper_component.k = 2

    # Execute search
    result = google_serper_component.search_serper()

    # Verify results
    assert isinstance(result, DataFrame)
    assert len(result) == 2
    assert list(result.columns) == ["title", "link", "snippet"]
    assert result.iloc[0]["title"] == "Test Title 1"
    assert result.iloc[1]["link"] == "https://test2.com"


@patch("langchain_community.utilities.google_serper.requests.get")
@patch("langchain_community.utilities.google_serper.requests.post")
def test_search_serper_error_handling(mock_post, mock_get, google_serper_component):
    # Configure mocks to simulate error
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.raise_for_status.side_effect = ConnectionError("API connection failed")
    mock_post.return_value = mock_response
    mock_get.return_value = mock_response

    # Configure component
    google_serper_component.serper_api_key = "test_api_key"
    google_serper_component.input_value = "test query"
    google_serper_component.k = 2

    # Execute search
    result = google_serper_component.search_serper()

    # Verify error handling
    assert isinstance(result, DataFrame)
    assert "error" in result.columns
    assert "API connection failed" in result.iloc[0]["error"]


def test_text_search_serper(google_serper_component):
    with patch.object(google_serper_component, "search_serper") as mock_search:
        mock_search.return_value = DataFrame(
            [{"title": "Test Title", "link": "https://test.com", "snippet": "Test snippet"}]
        )

        result = google_serper_component.text_search_serper()
        assert result.text is not None
        assert "Test Title" in result.text
        assert "https://test.com" in result.text


def test_build_wrapper(google_serper_component):
    google_serper_component.serper_api_key = "test_api_key"
    google_serper_component.k = 2

    wrapper = google_serper_component._build_wrapper()
    assert wrapper.serper_api_key == "test_api_key"
    assert wrapper.k == 2


def test_build_method(google_serper_component):
    build_result = google_serper_component.build()
    assert build_result == google_serper_component.search_serper
