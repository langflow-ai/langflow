import pytest
from langflow.components.tools.serp import SerpComponent

from tests.base import ComponentTestBaseWithoutClient


class TestSerpComponent(ComponentTestBaseWithoutClient):
    """Test the Serp Search API component."""

    @pytest.fixture
    def component_class(self):
        """Return the class of the component to be tested."""
        return SerpComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default arguments required to instantiate the component."""
        return {
            "serpapi_api_key": "test_api_key",
            "input_value": "test query",
            "search_params": {"num": 5},
            "max_results": 5,
            "max_snippet_length": 100,
            "_session_id": "test_session",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the mapping of versions and file names for the component."""
        # Since this appears to be a new component, we can return an empty list
        return []

    def test_component_initialization(self, component_class, default_kwargs):
        """Test if the component initializes correctly with default arguments."""
        component = component_class(**default_kwargs)
        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]

        # Test component attributes
        assert node_data["display_name"] == "Serp Search API"
        assert node_data["description"] == "Call Serp Search API and return results as a DataFrame"
        assert node_data["base_classes"] == ["DataFrame"]

        # Test input fields
        template_fields = node_data["template"]
        assert "serpapi_api_key" in template_fields
        assert "input_value" in template_fields
        assert "search_params" in template_fields
        assert "max_results" in template_fields
        assert "max_snippet_length" in template_fields

        # Test input field properties
        assert template_fields["serpapi_api_key"]["type"] == "str"
        assert template_fields["serpapi_api_key"]["required"] is True
        assert template_fields["max_results"]["value"] == 5
        assert template_fields["max_snippet_length"]["value"] == 100

    def test_invalid_api_key(self, component_class, default_kwargs):
        """Test component behavior with invalid API key."""
        default_kwargs["serpapi_api_key"] = ""
        component = component_class(**default_kwargs)

        result = component.search_serp()
        assert len(result) == 1
        assert result.iloc[0]["error"] == "Invalid SerpAPI Key"

    def test_search_params_default(self, component_class, default_kwargs):
        """Test component with default search parameters."""
        # Remove search_params to test default behavior
        default_kwargs.pop("search_params")
        component = component_class(**default_kwargs)

        # Verify that the component uses empty dict as default
        assert component.search_params == {}
