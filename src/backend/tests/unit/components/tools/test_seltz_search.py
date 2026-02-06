import sys
from unittest.mock import MagicMock

import pytest

from tests.base import ComponentTestBaseWithoutClient


@pytest.fixture(autouse=True)
def mock_seltz_module():
    """Provide a mock seltz module so the component can be imported without the real package."""
    mock_module = MagicMock()
    mock_types = MagicMock()
    sys.modules["seltz"] = mock_module
    sys.modules["seltz.types"] = mock_types
    mock_module.types = mock_types
    yield mock_module
    sys.modules.pop("seltz", None)
    sys.modules.pop("seltz.types", None)


class TestSeltzSearchToolkit(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        from lfx.components.seltz.seltz_search import SeltzSearchToolkit

        return SeltzSearchToolkit

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test-api-key",
            "max_documents": 10,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_build_toolkit_returns_tools(self, mock_seltz_module, component_class, default_kwargs):
        mock_seltz_module.Seltz.return_value = MagicMock()

        component = component_class(**default_kwargs)
        tools = component.build_toolkit()

        mock_seltz_module.Seltz.assert_called_once_with(api_key="test-api-key")
        assert isinstance(tools, list)
        assert len(tools) == 1
        assert tools[0].name == "seltz_search"

    def test_search_tool_returns_documents(self, mock_seltz_module, component_class, default_kwargs):
        mock_client = MagicMock()
        mock_doc1 = MagicMock()
        mock_doc1.url = "https://example.com/1"
        mock_doc1.content = "First result"
        mock_doc2 = MagicMock()
        mock_doc2.url = "https://example.com/2"
        mock_doc2.content = "Second result"
        mock_response = MagicMock()
        mock_response.documents = [mock_doc1, mock_doc2]
        mock_client.search.return_value = mock_response
        mock_seltz_module.Seltz.return_value = mock_client

        component = component_class(**default_kwargs)
        tools = component.build_toolkit()
        result = tools[0].invoke({"query": "test query"})

        mock_includes = sys.modules["seltz.types"].Includes.return_value
        mock_client.search.assert_called_once_with(
            "test query", includes=mock_includes, context=None, profile=None
        )
        assert len(result) == 2
        assert result[0] == {"url": "https://example.com/1", "content": "First result"}
        assert result[1] == {"url": "https://example.com/2", "content": "Second result"}

    def test_custom_max_documents(self, mock_seltz_module, component_class):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.documents = []
        mock_client.search.return_value = mock_response
        mock_seltz_module.Seltz.return_value = mock_client

        component = component_class(api_key="test-key", max_documents=3)
        tools = component.build_toolkit()
        tools[0].invoke({"query": "test"})

        sys.modules["seltz.types"].Includes.assert_called_with(max_documents=3)
        mock_includes = sys.modules["seltz.types"].Includes.return_value
        mock_client.search.assert_called_once_with("test", includes=mock_includes, context=None, profile=None)

    def test_context_and_profile_passed_through(self, mock_seltz_module, component_class):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.documents = []
        mock_client.search.return_value = mock_response
        mock_seltz_module.Seltz.return_value = mock_client

        component = component_class(
            api_key="test-key",
            max_documents=5,
            context="user is looking for Python docs",
            profile="technical",
        )
        tools = component.build_toolkit()
        tools[0].invoke({"query": "python tutorial"})

        mock_includes = sys.modules["seltz.types"].Includes.return_value
        mock_client.search.assert_called_once_with(
            "python tutorial",
            includes=mock_includes,
            context="user is looking for Python docs",
            profile="technical",
        )

    def test_empty_context_and_profile_become_none(self, mock_seltz_module, component_class):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.documents = []
        mock_client.search.return_value = mock_response
        mock_seltz_module.Seltz.return_value = mock_client

        component = component_class(api_key="test-key", max_documents=10, context="", profile="")
        tools = component.build_toolkit()
        tools[0].invoke({"query": "test"})

        mock_includes = sys.modules["seltz.types"].Includes.return_value
        mock_client.search.assert_called_once_with("test", includes=mock_includes, context=None, profile=None)

    def test_search_empty_results(self, mock_seltz_module, component_class, default_kwargs):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.documents = []
        mock_client.search.return_value = mock_response
        mock_seltz_module.Seltz.return_value = mock_client

        component = component_class(**default_kwargs)
        tools = component.build_toolkit()
        result = tools[0].invoke({"query": "no results query"})

        assert result == []
