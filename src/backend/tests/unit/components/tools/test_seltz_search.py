import sys
from unittest.mock import MagicMock

import pytest

from tests.base import ComponentTestBaseWithoutClient


class _SeltzAuthenticationError(Exception):
    pass


class _SeltzRateLimitError(Exception):
    pass


class _SeltzConnectionError(Exception):
    pass


@pytest.fixture(autouse=True)
def mock_seltz_module():
    """Provide a mock seltz module so the component can be imported without the real package."""
    mock_module = MagicMock()
    mock_module.SeltzAuthenticationError = _SeltzAuthenticationError
    mock_module.SeltzRateLimitError = _SeltzRateLimitError
    mock_module.SeltzConnectionError = _SeltzConnectionError
    sys.modules["seltz"] = mock_module
    yield mock_module
    sys.modules.pop("seltz", None)


class TestSeltzSearchToolkit(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        from lfx.components.seltz.seltz_search import SeltzSearchToolkit

        return SeltzSearchToolkit

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test-api-key",  # pragma: allowlist secret
            "max_documents": 10,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_build_toolkit_returns_tools(self, mock_seltz_module, component_class, default_kwargs):
        mock_seltz_module.Seltz.return_value = MagicMock()

        component = component_class(**default_kwargs)
        tools = component.build_toolkit()

        mock_seltz_module.Seltz.assert_called_once_with(api_key="test-api-key")  # pragma: allowlist secret
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

        mock_includes = sys.modules["seltz"].Includes.return_value
        mock_client.search.assert_called_once_with("test query", includes=mock_includes, context=None, profile=None)
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

        sys.modules["seltz"].Includes.assert_called_with(max_documents=3)
        mock_includes = sys.modules["seltz"].Includes.return_value
        mock_client.search.assert_called_once_with("test", includes=mock_includes, context=None, profile=None)

    def test_context_and_profile_passed_through(self, mock_seltz_module, component_class):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.documents = []
        mock_client.search.return_value = mock_response
        mock_seltz_module.Seltz.return_value = mock_client

        component = component_class(
            api_key="test-key",  # pragma: allowlist secret
            max_documents=5,
            context="user is looking for Python docs",
            profile="technical",
        )
        tools = component.build_toolkit()
        tools[0].invoke({"query": "python tutorial"})

        mock_includes = sys.modules["seltz"].Includes.return_value
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

        mock_includes = sys.modules["seltz"].Includes.return_value
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

    def test_import_error_raised_when_seltz_not_installed(self, component_class, default_kwargs):
        """Verify a helpful ImportError is raised when the seltz package is missing."""
        import builtins
        from unittest.mock import patch

        original_import = builtins.__import__

        def fail_import(name, *args, **kwargs):
            if name == "seltz":
                msg = "No module named 'seltz'"
                raise ImportError(msg)
            return original_import(name, *args, **kwargs)

        component = component_class(**default_kwargs)
        with (
            patch("builtins.__import__", side_effect=fail_import),
            pytest.raises(ImportError, match="Could not import seltz package"),
        ):
            component.build_toolkit()

    def test_search_api_error_raises_runtime_error(self, mock_seltz_module, component_class, default_kwargs):
        """Verify that a Seltz API error is wrapped in a RuntimeError."""
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("API timeout")
        mock_seltz_module.Seltz.return_value = mock_client

        component = component_class(**default_kwargs)
        tools = component.build_toolkit()
        with pytest.raises(RuntimeError, match="Seltz search failed: API timeout"):
            tools[0].invoke({"query": "test"})

    def test_authentication_error_message(self, mock_seltz_module, component_class, default_kwargs):
        """Verify that a SeltzAuthenticationError produces a clear error message."""
        mock_client = MagicMock()
        auth_error = mock_seltz_module.SeltzAuthenticationError("Invalid API key")
        mock_client.search.side_effect = auth_error
        mock_seltz_module.Seltz.return_value = mock_client

        component = component_class(**default_kwargs)
        tools = component.build_toolkit()
        with pytest.raises(RuntimeError, match="Seltz authentication failed"):
            tools[0].invoke({"query": "test"})

    def test_rate_limit_error_message(self, mock_seltz_module, component_class, default_kwargs):
        """Verify that a SeltzRateLimitError produces a clear error message."""
        mock_client = MagicMock()
        rate_error = mock_seltz_module.SeltzRateLimitError("Too many requests")
        mock_client.search.side_effect = rate_error
        mock_seltz_module.Seltz.return_value = mock_client

        component = component_class(**default_kwargs)
        tools = component.build_toolkit()
        with pytest.raises(RuntimeError, match="Seltz rate limit exceeded"):
            tools[0].invoke({"query": "test"})

    def test_connection_error_message(self, mock_seltz_module, component_class, default_kwargs):
        """Verify that a SeltzConnectionError produces a clear error message."""
        mock_client = MagicMock()
        conn_error = mock_seltz_module.SeltzConnectionError("Connection refused")
        mock_client.search.side_effect = conn_error
        mock_seltz_module.Seltz.return_value = mock_client

        component = component_class(**default_kwargs)
        tools = component.build_toolkit()
        with pytest.raises(RuntimeError, match="Failed to connect to Seltz API"):
            tools[0].invoke({"query": "test"})
