from unittest.mock import MagicMock

import pytest
from langflow.components.tools import WikipediaAPIComponent
from langflow.custom import Component
from langflow.custom.utils import build_custom_component_template
from langflow.schema import Data
from langflow.schema.message import Message


def test_wikipedia_initialization():
    component = WikipediaAPIComponent()
    assert component.display_name == "Wikipedia API"
    assert component.description == "Call Wikipedia API."
    assert component.icon == "Wikipedia"


def test_wikipedia_template():
    wikipedia = WikipediaAPIComponent()
    component = Component(_code=wikipedia._code)
    frontend_node, _ = build_custom_component_template(component)

    # Verify basic structure
    assert isinstance(frontend_node, dict)

    # Verify inputs
    assert "template" in frontend_node
    input_names = [input_["name"] for input_ in frontend_node["template"].values() if isinstance(input_, dict)]

    expected_inputs = ["input_value", "lang", "k", "load_all_available_meta", "doc_content_chars_max"]

    for input_name in expected_inputs:
        assert input_name in input_names


@pytest.fixture
def mock_wikipedia_wrapper(mocker):
    return mocker.patch("langchain_community.utilities.wikipedia.WikipediaAPIWrapper")


def test_fetch_content(mock_wikipedia_wrapper):
    component = WikipediaAPIComponent()
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


def test_fetch_content_text():
    component = WikipediaAPIComponent()
    component.fetch_content = MagicMock(return_value=[Data(text="First result"), Data(text="Second result")])

    result = component.fetch_content_text()

    assert isinstance(result, Message)
    assert result.text == "First result\nSecond result\n"


def test_wikipedia_error_handling():
    component = WikipediaAPIComponent()

    # Mock _build_wrapper to raise exception
    component._build_wrapper = MagicMock(side_effect=Exception("API Error"))

    with pytest.raises(Exception, match="API Error"):
        component.fetch_content()
