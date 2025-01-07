from unittest.mock import MagicMock, patch

import httpx
import pytest
from langchain_core.tools import ToolException
from langflow.components.tools import WikidataAPIComponent
from langflow.custom import Component
from langflow.custom.utils import build_custom_component_template
from langflow.schema import Data
from langflow.schema.message import Message


def test_wikidata_initialization():
    component = WikidataAPIComponent()
    assert component.display_name == "Wikidata API"
    assert component.description == "Performs a search using the Wikidata API."
    assert component.icon == "Wikipedia"


def test_wikidata_template():
    wikidata = WikidataAPIComponent()
    component = Component(_code=wikidata._code)
    frontend_node, _ = build_custom_component_template(component)

    # Verify basic structure
    assert isinstance(frontend_node, dict)

    # Verify inputs
    assert "template" in frontend_node
    input_names = [input_["name"] for input_ in frontend_node["template"].values() if isinstance(input_, dict)]
    assert "query" in input_names


@patch("langflow.components.tools.wikidata_api.httpx.get")
def test_fetch_content_success(mock_httpx):
    component = WikidataAPIComponent()
    component.query = "test query"

    # Mock successful API response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "search": [
            {
                "label": "Test Label",
                "id": "Q123",
                "url": "https://test.com",
                "description": "Test Description",
                "concepturi": "https://test.com/concept",
            }
        ]
    }
    mock_httpx.return_value = mock_response

    result = component.fetch_content()

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].text == "Test Label: Test Description"
    assert result[0].data["label"] == "Test Label"
    assert result[0].data["id"] == "Q123"


@patch("langflow.components.tools.wikidata_api.httpx.get")
def test_fetch_content_empty_response(mock_httpx):
    component = WikidataAPIComponent()
    component.query = "test query"

    # Mock empty API response
    mock_response = MagicMock()
    mock_response.json.return_value = {"search": []}
    mock_httpx.return_value = mock_response

    result = component.fetch_content()

    assert isinstance(result, list)
    assert len(result) == 1
    assert "error" in result[0].data
    assert "No search results found" in result[0].data["error"]


@patch("langflow.components.tools.wikidata_api.httpx.get")
def test_fetch_content_error_handling(mock_httpx):
    component = WikidataAPIComponent()
    component.query = "test query"

    # Mock HTTP error
    mock_httpx.side_effect = httpx.HTTPError("API Error")

    with pytest.raises(ToolException):
        component.fetch_content()


def test_fetch_content_text():
    component = WikidataAPIComponent()
    component.fetch_content = MagicMock(
        return_value=[
            Data(text="First result", data={"label": "Label 1"}),
            Data(text="Second result", data={"label": "Label 2"}),
        ]
    )

    result = component.fetch_content_text()

    assert isinstance(result, Message)
    assert "First result" in result.text
    assert "Second result" in result.text
