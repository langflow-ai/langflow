from unittest.mock import patch

import pandas as pd
import pytest
from lfx.components.google.google_search_api_core import GoogleSearchAPICore
from lfx.schema import DataFrame

from tests.base import ComponentTestBaseWithoutClient


class TestGoogleSearchAPICore(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return GoogleSearchAPICore

    @pytest.fixture
    def default_kwargs(self):
        return {
            "google_api_key": "test_api_key",
            "google_cse_id": "test_cse_id",
            "input_value": "test query",
            "k": 2,
        }

    @pytest.fixture
    def file_names_mapping(self):
        # New component, no previous versions
        return []

    @pytest.fixture
    def mock_search_results(self):
        return pd.DataFrame(
            [
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
        )

    def test_component_initialization(self, component_class):
        component = component_class()

        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]

        # Test basic component attributes
        assert node_data["display_name"] == "Google Search API"
        assert node_data["icon"] == "Google"

        # Test inputs configuration
        template = node_data["template"]
        assert "google_api_key" in template
        assert "google_cse_id" in template
        assert "input_value" in template
        assert "k" in template

    @patch("langchain_google_community.GoogleSearchAPIWrapper.results")
    def test_search_google_success(self, mock_results, component_class, default_kwargs, mock_search_results):
        component = component_class(**default_kwargs)
        mock_results.return_value = mock_search_results.to_dict("records")

        result = component.search_google()

        assert isinstance(result, DataFrame)
        assert len(result) == 2
        assert result.iloc[0]["title"] == "Test Title 1"
        assert result.iloc[1]["link"] == "https://test2.com"
        mock_results.assert_called_once_with(query="test query", num_results=2)

    def test_search_google_invalid_api_key(self, component_class):
        component = component_class(google_api_key=None)
        result = component.search_google()

        assert isinstance(result, DataFrame)
        assert "error" in result.columns
        assert "Invalid Google API Key" in result.iloc[0]["error"]

    def test_search_google_invalid_cse_id(self, component_class):
        component = component_class(google_api_key="valid_key", google_cse_id=None)
        result = component.search_google()

        assert isinstance(result, DataFrame)
        assert "error" in result.columns
        assert "Invalid Google CSE ID" in result.iloc[0]["error"]

    @patch("langchain_google_community.GoogleSearchAPIWrapper.results")
    def test_search_google_error_handling(self, mock_results, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        mock_results.side_effect = ConnectionError("API connection failed")

        result = component.search_google()

        assert isinstance(result, DataFrame)
        assert "error" in result.columns
        assert "Connection error: API connection failed" in result.iloc[0]["error"]

    def test_build_method(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_result = component.build()
        assert build_result == component.search_google

    @pytest.mark.asyncio
    async def test_latest_version(self, component_class, default_kwargs):
        """Override test_latest_version to skip API call."""
        component = component_class(**default_kwargs)
        assert component is not None
