from unittest.mock import patch

import pytest
from langflow.components.tools import DuckDuckGoSearchCoreComponent
from langflow.schema import DataFrame

from tests.base import ComponentTestBaseWithoutClient


class TestDuckDuckGoSearchCoreComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return DuckDuckGoSearchCoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"input_value": "test query", "max_snippet_length": 500, "_session_id": "test_session"}

    @pytest.fixture
    def file_names_mapping(self):
        # New component, no previous versions
        return []

    @pytest.fixture
    def mock_search_results(self):
        # Return a list of dictionaries simulating the real format
        return [
            {"snippet": "Result 1", "link": "http://example1.com"},
            {"snippet": "Result 2", "link": "http://example2.com"},
            {"snippet": "Result 3", "link": "http://example3.com"},
        ]

    def test_component_initialization(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]

        assert node_data["display_name"] == "DuckDuckGo Search"
        assert node_data["icon"] == "DuckDuckGo"

    @patch("langchain_community.tools.DuckDuckGoSearchResults.invoke")
    def test_search_duckduckgo_success(self, mock_invoke, component_class, default_kwargs, mock_search_results):
        # Configure mock
        mock_invoke.return_value = mock_search_results

        # Configure component
        component = component_class(**default_kwargs)

        # Execute search
        result = component.search_duckduckgo()

        # Verify results
        assert isinstance(result, DataFrame)
        assert len(result) == 3
        assert "text" in result.columns
        assert all(len(text) <= 500 for text in result["text"])

    @patch("langchain_community.tools.DuckDuckGoSearchResults.invoke")
    def test_search_duckduckgo_error_handling(self, mock_invoke, component_class, default_kwargs):
        # Configure mock to simulate error
        mock_invoke.side_effect = RuntimeError("Search failed")

        # Configure component
        component = component_class(**default_kwargs)

        # Execute search
        result = component.search_duckduckgo()

        # Verify error handling
        assert isinstance(result, DataFrame)
        assert "text" in result.columns
        assert "Error in DuckDuckGo Search" in result.iloc[0]["text"]

    def test_build_method(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_result = component.build()
        assert build_result == component.search_duckduckgo
