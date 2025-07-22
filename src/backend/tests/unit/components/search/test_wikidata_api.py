from unittest.mock import MagicMock, patch

import httpx
import pytest
from langchain_core.tools import ToolException
from langflow.custom import Component
from langflow.custom.utils import build_custom_component_template

from lfx.components.wikipedia import WikidataComponent

# Import the base test class
from tests.base import ComponentTestBaseWithoutClient


class TestWikidataComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Fixture to create a WikidataComponent instance."""
        return WikidataComponent

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    @pytest.fixture
    def mock_query(self):
        """Fixture to provide a default query."""
        return "test query"

    def test_wikidata_initialization(self, component_class):
        component = component_class()
        assert component.display_name == "Wikidata"
        assert component.description == "Performs a search using the Wikidata API."
        assert component.icon == "Wikipedia"

    def test_wikidata_template(self, component_class):
        component = component_class()
        frontend_node, _ = build_custom_component_template(Component(_code=component._code))

        # Verify basic structure
        assert isinstance(frontend_node, dict)

        # Verify inputs
        assert "template" in frontend_node
        input_names = [input_["name"] for input_ in frontend_node["template"].values() if isinstance(input_, dict)]
        assert "query" in input_names

    @patch("lfx.components.tools.wikidata_api.httpx.get")
    def test_fetch_content_success(self, mock_httpx, component_class, mock_query):
        component = component_class()
        component.query = mock_query

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

    @patch("lfx.components.tools.wikidata_api.httpx.get")
    def test_fetch_content_empty_response(self, mock_httpx, component_class, mock_query):
        component = component_class()
        component.query = mock_query

        # Mock empty API response
        mock_response = MagicMock()
        mock_response.json.return_value = {"search": []}
        mock_httpx.return_value = mock_response

        result = component.fetch_content()

        assert isinstance(result, list)
        assert len(result) == 1
        assert "error" in result[0].data
        assert "No search results found" in result[0].data["error"]

    @patch("lfx.components.tools.wikidata_api.httpx.get")
    def test_fetch_content_error_handling(self, mock_httpx, component_class, mock_query):
        component = component_class()
        component.query = mock_query

        # Mock HTTP error
        mock_httpx.side_effect = httpx.HTTPError("API Error")

        with pytest.raises(ToolException):
            component.fetch_content()
