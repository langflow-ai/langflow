import pytest

from langflow.components.tools import GoogleSearchAPICore
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestGoogleSearchAPICore(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return GoogleSearchAPICore

    @pytest.fixture
    def default_kwargs(self):
        return {
            "google_api_key": "test_api_key",
            "google_cse_id": "test_cse_id",
            "input_value": "test query",
            "k": 4,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "google_search_api", "file_name": "GoogleSearchAPICore"},
        ]

    def test_search_google_valid(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.search_google()
        assert result is not None
        assert isinstance(result, DataFrame)

    def test_search_google_invalid_api_key(self, component_class):
        component = component_class(google_api_key="", google_cse_id="test_cse_id", input_value="test query", k=4)
        result = component.search_google()
        assert result is not None
        assert result.to_dict() == [{"error": "Invalid Google API Key"}]

    def test_search_google_invalid_cse_id(self, component_class):
        component = component_class(google_api_key="test_api_key", google_cse_id="", input_value="test query", k=4)
        result = component.search_google()
        assert result is not None
        assert result.to_dict() == [{"error": "Invalid Google CSE ID"}]

    def test_search_google_exception_handling(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.google_api_key = "invalid_key"  # Simulate an invalid key scenario
        result = component.search_google()
        assert result is not None
        assert "error" in result.to_dict()[0]
