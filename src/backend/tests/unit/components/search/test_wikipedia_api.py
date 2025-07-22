from unittest.mock import MagicMock

import pytest
from langflow.custom import Component
from langflow.custom.utils import build_custom_component_template

from lfx.components.wikipedia import WikipediaComponent

# Import the base test class
from tests.base import ComponentTestBaseWithoutClient


class TestWikipediaComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Fixture to create a WikipediaComponent instance."""
        return WikipediaComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "input_value": "test query",
            "lang": "en",
            "k": 3,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    def test_wikipedia_initialization(self, component_class):
        component = component_class()
        assert component.display_name == "Wikipedia"
        assert component.description == "Call Wikipedia API."
        assert component.icon == "Wikipedia"

    def test_wikipedia_template(self, component_class):
        component = component_class()
        frontend_node, _ = build_custom_component_template(Component(_code=component._code))

        # Verify basic structure
        assert isinstance(frontend_node, dict)

        # Verify inputs
        assert "template" in frontend_node
        input_names = [input_["name"] for input_ in frontend_node["template"].values() if isinstance(input_, dict)]

        expected_inputs = ["input_value", "lang", "k", "load_all_available_meta", "doc_content_chars_max"]

        for input_name in expected_inputs:
            assert input_name in input_names

    @pytest.fixture
    def mock_wikipedia_wrapper(self, mocker):
        return mocker.patch("langchain_community.utilities.wikipedia.WikipediaAPIWrapper")

    def test_fetch_content(self, component_class, mock_wikipedia_wrapper):
        component = component_class()
        component.input_value = "test query"
        component.k = 3
        component.lang = "en"

        # Mock the WikipediaAPIWrapper and its load method
        mock_instance = MagicMock()
        mock_wikipedia_wrapper.return_value = mock_instance
        mock_doc = MagicMock()
        mock_doc.page_content = "Test content"
        mock_doc.metadata = {"source": "wikipedia", "title": "Test Page"}
        mock_instance.load.return_value = [mock_doc]

        # Mock the _build_wrapper method to return our mock instance
        component._build_wrapper = MagicMock(return_value=mock_instance)

        result = component.fetch_content()

        # Verify wrapper was built with correct params
        component._build_wrapper.assert_called_once()
        mock_instance.load.assert_called_once_with("test query")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].text == "Test content"

    def test_wikipedia_error_handling(self, component_class):
        component = component_class()
        # Mock _build_wrapper to raise exception
        component._build_wrapper = MagicMock(side_effect=Exception("API Error"))

        with pytest.raises(Exception, match="API Error"):
            component.fetch_content()
