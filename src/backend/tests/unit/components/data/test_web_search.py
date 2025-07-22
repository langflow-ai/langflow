import pytest
from langflow.schema import DataFrame

from lfx.components.data.web_search import WebSearchComponent
from tests.base import ComponentTestBaseWithoutClient


class TestWebSearchComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return WebSearchComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "query": "OpenAI GPT-4",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for the component."""
        return []

    async def test_invalid_url_handling(self):
        # Create a test instance of the component
        component = WebSearchComponent()

        # Set an invalid URL
        invalid_url = "htp://invalid-url"

        # Ensure the URL is invalid
        with pytest.raises(ValueError, match="Invalid URL"):
            component.ensure_url(invalid_url)

    def test_successful_web_search(self):
        component = WebSearchComponent()
        component.query = "OpenAI GPT-4"
        result = component.perform_search()
        assert isinstance(result, DataFrame)
        assert not result.empty
