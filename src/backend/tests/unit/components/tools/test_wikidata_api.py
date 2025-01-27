from unittest.mock import MagicMock, patch

import httpx
import pytest
from langflow.components.tools import WikidataComponent
from langflow.custom import Component
from langflow.custom.utils import build_custom_component_template
from langflow.schema import DataFrame

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

    @patch("httpx.get")
    def test_search_wikidata_success(self, mock_httpx, component_class, mock_query):
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

        result = component.search_wikidata()

        assert isinstance(result, DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["label"] == "Test Label"
        assert result.iloc[0]["id"] == "Q123"
        assert result.iloc[0]["full_text"] == "Test Label: Test Description"

    @patch("httpx.get")
    def test_search_wikidata_empty_response(self, mock_httpx, component_class, mock_query):
        component = component_class()
        component.query = mock_query

        # Mock empty API response
        mock_response = MagicMock()
        mock_response.json.return_value = {"search": []}
        mock_httpx.return_value = mock_response

        result = component.search_wikidata()

        assert isinstance(result, DataFrame)
        assert len(result) == 1
        assert "error" in result.columns
        assert "No search results found" in result.iloc[0]["error"]

    @patch("httpx.get")
    def test_search_wikidata_error_handling(self, mock_httpx, component_class, mock_query):
        component = component_class()
        component.query = mock_query

        # Mock HTTP error usando RequestError ao invés de HTTPError
        mock_httpx.side_effect = httpx.RequestError("API Error")

        result = component.search_wikidata()
        
        assert isinstance(result, DataFrame)
        assert len(result) == 1
        assert "error" in result.columns
        assert "Connection error" in result.iloc[0]["error"]
