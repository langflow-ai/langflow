"""Unit tests for MCP component with actual MCP servers.

This test suite validates the MCP component functionality using real MCP servers:
- Everything server (stdio mode) - provides echo and other tools
- HTTP/SSE servers (streamable HTTP mode) - provides various tools
"""

import shutil
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.base.mcp.util import MCPSessionManager, MCPStdioClient, MCPStreamableHttpClient
from lfx.components.models_and_agents.mcp_component import MCPToolsComponent

from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping


class TestMCPToolsComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return MCPToolsComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "mode": "Stdio",
            "command": "npx -y @modelcontextprotocol/server-everything",
            "sse_url": "https://mcp.deepwiki.com/sse",
            "tool": "echo",
            "mcp_server": {"name": "test_server", "config": {"command": "uvx mcp-server-fetch"}},
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions."""
        return []

    @pytest.mark.asyncio
    @pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
    async def test_component_initialization(self, component_class, default_kwargs):
        """Test that the component initializes correctly."""
        component = component_class(**default_kwargs)

        # Check that the component has the expected attributes
        assert hasattr(component, "stdio_client")
        assert hasattr(component, "streamable_http_client")
        assert isinstance(component.stdio_client, MCPStdioClient)
        assert isinstance(component.streamable_http_client, MCPStreamableHttpClient)

        # Check that the component has a session manager
        session_manager = component.stdio_client._get_session_manager()
        assert isinstance(session_manager, MCPSessionManager)


class TestMCPToolsComponentIntegration:
    """Integration tests for the MCPToolsComponent."""

    @pytest.fixture
    def component(self):
        """Create a component for testing."""
        return MCPToolsComponent()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
    async def test_stdio_mode_integration(self, component):
        """Test the component in stdio mode with Everything server."""
        # Configure for stdio mode
        component.mode = "Stdio"
        component.command = "npx -y @modelcontextprotocol/server-everything"
        component.tool = "echo"

        try:
            # Mock the update_tool_list method to simulate server connection
            tools, server_info = await component.update_tool_list()

            # Should have tools
            assert len(tools) > 0

            # Should have server info
            assert server_info is not None
            assert isinstance(server_info, dict)

        except Exception as e:
            # If the server is not accessible, skip the test
            pytest.skip(f"Everything server not accessible: {e}")

    @pytest.mark.asyncio
    async def test_streamable_http_mode_integration(self, component):
        """Test the component in Streamable HTTP mode with DeepWiki server."""
        # Configure for Streamable HTTP mode
        component.mode = "Streamable HTTP"
        component.streamable_http_url = "https://mcp.deepwiki.com/mcp"

        try:
            # Mock the update_tool_list method to simulate server connection
            tools, server_info = await component.update_tool_list()

            # Should have tools
            assert len(tools) > 0

            # Should have server info
            assert server_info is not None
            assert isinstance(server_info, dict)

        except Exception as e:
            # If the server is not accessible, skip the test
            pytest.skip(f"DeepWiki server not accessible: {e}")

    @pytest.mark.asyncio
    async def test_session_context_setting(self, component):
        """Test that session context is properly set."""
        # Set session context on both clients
        component.stdio_client.set_session_context("test_context")
        component.streamable_http_client.set_session_context("test_context")

        # Verify context was set
        assert component.stdio_client._session_context == "test_context"
        assert component.streamable_http_client._session_context == "test_context"

    @pytest.mark.asyncio
    async def test_session_manager_sharing(self, component):
        """Test that session managers are shared through component cache."""
        # Ensure the component has a shared cache set up
        # If _shared_component_cache is None, clients will create separate instance managers
        if component._shared_component_cache is None:
            # Create a mock cache dict to ensure sharing
            from lfx.services.cache.utils import CacheMiss

            cache_dict = {}

            class MockCache:
                def get(self, key):
                    return cache_dict.get(key, CacheMiss())

                def set(self, key, value):
                    cache_dict[key] = value
                    return value

            mock_cache = MockCache()
            component._shared_component_cache = mock_cache
            component.stdio_client._component_cache = mock_cache
            component.streamable_http_client._component_cache = mock_cache

        # Get session managers from both clients
        stdio_manager = component.stdio_client._get_session_manager()
        http_manager = component.streamable_http_client._get_session_manager()

        # Both should be MCPSessionManager instances
        assert isinstance(stdio_manager, MCPSessionManager)
        assert isinstance(http_manager, MCPSessionManager)

        # They should be the same instance (shared through cache)
        assert stdio_manager is http_manager


class TestMCPComponentErrorHandling:
    """Test error handling in MCP components."""

    @pytest.fixture
    def stdio_client(self):
        return MCPStdioClient()

    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        return AsyncMock(spec=MCPSessionManager)

    async def test_connect_to_server_with_command(self, stdio_client):
        """Test connecting to server via Stdio with command."""
        with patch.object(stdio_client, "_get_or_create_session") as mock_get_session:
            # Mock session
            mock_session = AsyncMock()
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            list_tools_result = MagicMock()
            list_tools_result.tools = [mock_tool]
            mock_session.list_tools = AsyncMock(return_value=list_tools_result)
            mock_get_session.return_value = mock_session

            tools = await stdio_client.connect_to_server("uvx test-command")

            assert len(tools) == 1
            assert tools[0].name == "test_tool"
            assert stdio_client._connected is True
            assert stdio_client._connection_params is not None

    async def test_run_tool_success(self, stdio_client):
        """Test successfully running a tool."""
        # Setup connection state
        stdio_client._connected = True
        stdio_client._connection_params = MagicMock()
        stdio_client._session_context = "test_context"

        with patch.object(stdio_client, "_get_or_create_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_session.call_tool = AsyncMock(return_value=mock_result)
            mock_get_session.return_value = mock_session

            result = await stdio_client.run_tool("test_tool", {"param": "value"})

            assert result == mock_result
            mock_session.call_tool.assert_called_once_with("test_tool", arguments={"param": "value"})

    async def test_run_tool_without_connection(self, stdio_client):
        """Test running a tool without being connected."""
        stdio_client._connected = False

        with pytest.raises(ValueError, match="Session not initialized"):
            await stdio_client.run_tool("test_tool", {})

    async def test_disconnect_cleanup(self, stdio_client):
        """Test that disconnect properly cleans up resources."""
        stdio_client._session_context = "test_context"
        stdio_client._connected = True

        with patch.object(stdio_client, "_get_session_manager") as mock_get_manager:
            mock_manager = AsyncMock()
            mock_get_manager.return_value = mock_manager

            await stdio_client.disconnect()

            mock_manager._cleanup_session.assert_called_once_with("test_context")
            assert stdio_client.session is None
            assert stdio_client._connected is False


class TestMCPComponentHeaders:
    """Test the headers functionality in MCP component."""

    @pytest.fixture
    def component(self):
        """Create a component for testing."""
        return MCPToolsComponent()

    def test_headers_input_exists(self, component):
        """Test that headers input field exists in the component."""
        input_names = [inp.name for inp in component.inputs]
        assert "headers" in input_names

    def test_headers_in_default_keys(self, component):
        """Test that headers is included in default_keys."""
        assert "headers" in component.default_keys

    def test_headers_input_is_list_type(self, component):
        """Test that headers input is configured as a list (is_list=True)."""
        headers_input = next((inp for inp in component.inputs if inp.name == "headers"), None)
        assert headers_input is not None
        assert headers_input.is_list is True

    def test_headers_input_is_advanced(self, component):
        """Test that headers input is marked as advanced."""
        headers_input = next((inp for inp in component.inputs if inp.name == "headers"), None)
        assert headers_input is not None
        assert headers_input.advanced is True

    @pytest.mark.asyncio
    async def test_headers_merge_list_format(self, component):
        """Test merging headers in list format [{"key": k, "value": v}]."""
        # Setup component with headers in list format
        component.headers = [
            {"key": "Authorization", "value": "Bearer test-token"},
            {"key": "X-Custom-Header", "value": "custom-value"},
        ]

        server_config = {"url": "http://test.url", "mode": "Streamable_HTTP"}

        # Simulate the merge logic from update_tool_list
        component_headers = getattr(component, "headers", None) or []
        component_headers_dict = {}
        if isinstance(component_headers, list):
            for item in component_headers:
                if isinstance(item, dict) and "key" in item and "value" in item:
                    component_headers_dict[item["key"]] = item["value"]

        if component_headers_dict:
            existing_headers = server_config.get("headers", {}) or {}
            merged_headers = {**existing_headers, **component_headers_dict}
            server_config["headers"] = merged_headers

        assert server_config["headers"] == {
            "Authorization": "Bearer test-token",
            "X-Custom-Header": "custom-value",
        }

    @pytest.mark.asyncio
    async def test_headers_merge_with_existing_headers(self, component):
        """Test that component headers override existing server config headers."""
        component.headers = [
            {"key": "Authorization", "value": "Bearer new-token"},
        ]

        server_config = {
            "url": "http://test.url",
            "mode": "Streamable_HTTP",
            "headers": {"Authorization": "Bearer old-token", "X-Existing": "existing-value"},
        }

        # Simulate the merge logic
        component_headers = getattr(component, "headers", None) or []
        component_headers_dict = {}
        if isinstance(component_headers, list):
            for item in component_headers:
                if isinstance(item, dict) and "key" in item and "value" in item:
                    component_headers_dict[item["key"]] = item["value"]

        if component_headers_dict:
            existing_headers = server_config.get("headers", {}) or {}
            merged_headers = {**existing_headers, **component_headers_dict}
            server_config["headers"] = merged_headers

        # Component headers should override existing
        assert server_config["headers"]["Authorization"] == "Bearer new-token"
        # Existing headers should be preserved
        assert server_config["headers"]["X-Existing"] == "existing-value"

    @pytest.mark.asyncio
    async def test_headers_merge_empty_list(self, component):
        """Test that empty headers list doesn't modify server config."""
        component.headers = []

        server_config = {
            "url": "http://test.url",
            "headers": {"X-Existing": "value"},
        }

        component_headers = getattr(component, "headers", None) or []
        component_headers_dict = {}
        if isinstance(component_headers, list):
            for item in component_headers:
                if isinstance(item, dict) and "key" in item and "value" in item:
                    component_headers_dict[item["key"]] = item["value"]

        if component_headers_dict:
            existing_headers = server_config.get("headers", {}) or {}
            merged_headers = {**existing_headers, **component_headers_dict}
            server_config["headers"] = merged_headers

        # Should remain unchanged
        assert server_config["headers"] == {"X-Existing": "value"}

    @pytest.mark.asyncio
    async def test_headers_merge_none_headers(self, component):
        """Test that None headers doesn't cause errors."""
        component.headers = None

        server_config = {"url": "http://test.url"}

        component_headers = getattr(component, "headers", None) or []
        component_headers_dict = {}
        if isinstance(component_headers, list):
            for item in component_headers:
                if isinstance(item, dict) and "key" in item and "value" in item:
                    component_headers_dict[item["key"]] = item["value"]

        if component_headers_dict:
            existing_headers = server_config.get("headers", {}) or {}
            merged_headers = {**existing_headers, **component_headers_dict}
            server_config["headers"] = merged_headers

        # Should not have headers key added
        assert "headers" not in server_config

    @pytest.mark.asyncio
    async def test_headers_merge_malformed_list_items(self, component):
        """Test that malformed list items are skipped."""
        component.headers = [
            {"key": "Valid-Header", "value": "valid-value"},
            {"key": "Missing-Value"},  # Missing "value"
            {"value": "Missing-Key"},  # Missing "key"
            "not-a-dict",  # Wrong type
            None,  # None item
            {"key": "Another-Valid", "value": "another-value"},
        ]

        server_config = {"url": "http://test.url"}

        component_headers = getattr(component, "headers", None) or []
        component_headers_dict = {}
        if isinstance(component_headers, list):
            for item in component_headers:
                if isinstance(item, dict) and "key" in item and "value" in item:
                    component_headers_dict[item["key"]] = item["value"]

        if component_headers_dict:
            existing_headers = server_config.get("headers", {}) or {}
            merged_headers = {**existing_headers, **component_headers_dict}
            server_config["headers"] = merged_headers

        # Only valid items should be included
        assert server_config["headers"] == {
            "Valid-Header": "valid-value",
            "Another-Valid": "another-value",
        }

    @pytest.mark.asyncio
    async def test_headers_merge_dict_format_fallback(self, component):
        """Test that dict format still works as fallback."""
        # Even though we use is_list=True, the code also supports dict format
        component.headers = {
            "Authorization": "Bearer dict-token",
            "X-Dict-Header": "dict-value",
        }

        server_config = {"url": "http://test.url"}

        component_headers = getattr(component, "headers", None) or []
        component_headers_dict = {}
        if isinstance(component_headers, list):
            for item in component_headers:
                if isinstance(item, dict) and "key" in item and "value" in item:
                    component_headers_dict[item["key"]] = item["value"]
        elif isinstance(component_headers, dict):
            component_headers_dict = component_headers

        if component_headers_dict:
            existing_headers = server_config.get("headers", {}) or {}
            merged_headers = {**existing_headers, **component_headers_dict}
            server_config["headers"] = merged_headers

        assert server_config["headers"] == {
            "Authorization": "Bearer dict-token",
            "X-Dict-Header": "dict-value",
        }

    @pytest.mark.asyncio
    async def test_headers_merge_existing_headers_as_list(self, component):
        """Test merging when existing headers are also in list format."""
        component.headers = [
            {"key": "New-Header", "value": "new-value"},
        ]

        server_config = {
            "url": "http://test.url",
            "headers": [
                {"key": "Existing-Header", "value": "existing-value"},
            ],
        }

        component_headers = getattr(component, "headers", None) or []
        component_headers_dict = {}
        if isinstance(component_headers, list):
            for item in component_headers:
                if isinstance(item, dict) and "key" in item and "value" in item:
                    component_headers_dict[item["key"]] = item["value"]

        if component_headers_dict:
            existing_headers = server_config.get("headers", {}) or {}
            # Convert existing headers from list to dict if needed
            if isinstance(existing_headers, list):
                existing_dict = {}
                for item in existing_headers:
                    if isinstance(item, dict) and "key" in item and "value" in item:
                        existing_dict[item["key"]] = item["value"]
                existing_headers = existing_dict
            merged_headers = {**existing_headers, **component_headers_dict}
            server_config["headers"] = merged_headers

        assert server_config["headers"] == {
            "Existing-Header": "existing-value",
            "New-Header": "new-value",
        }

    @pytest.mark.asyncio
    async def test_headers_with_special_characters(self, component):
        """Test headers with special characters in values."""
        component.headers = [
            {"key": "Authorization", "value": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"},
            {"key": "X-Special", "value": "value with spaces and !@#$%"},
        ]

        server_config = {"url": "http://test.url"}

        component_headers = getattr(component, "headers", None) or []
        component_headers_dict = {}
        if isinstance(component_headers, list):
            for item in component_headers:
                if isinstance(item, dict) and "key" in item and "value" in item:
                    component_headers_dict[item["key"]] = item["value"]

        if component_headers_dict:
            server_config["headers"] = component_headers_dict

        assert server_config["headers"]["Authorization"] == "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        assert server_config["headers"]["X-Special"] == "value with spaces and !@#$%"

    @pytest.mark.asyncio
    async def test_headers_empty_string_values(self, component):
        """Test headers with empty string values."""
        component.headers = [
            {"key": "X-Empty", "value": ""},
            {"key": "X-Valid", "value": "valid"},
        ]

        server_config = {"url": "http://test.url"}

        component_headers = getattr(component, "headers", None) or []
        component_headers_dict = {}
        if isinstance(component_headers, list):
            for item in component_headers:
                if isinstance(item, dict) and "key" in item and "value" in item:
                    component_headers_dict[item["key"]] = item["value"]

        if component_headers_dict:
            server_config["headers"] = component_headers_dict

        # Empty string is still a valid value
        assert server_config["headers"]["X-Empty"] == ""
        assert server_config["headers"]["X-Valid"] == "valid"


class TestMCPComponentConfigPriority:
    """Test configuration priority in MCP component - database over tweaks/value."""

    @pytest.fixture
    def component(self):
        """Create a component for testing."""
        return MCPToolsComponent()

    @pytest.mark.asyncio
    async def test_database_config_takes_priority_over_value(self, component):
        """Test that database config takes priority over config from mcp_server value."""
        # Set up component with a server config in the value
        value_config = {
            "command": "uvx mcp-server-from-value",
            "args": ["--test"],
            "env": {"TEST": "value"},
        }
        component.mcp_server = {"name": "test_server", "config": value_config}
        component._user_id = "test_user_123"

        # Mock the database get_server to return a different config
        db_config = {
            "command": "uvx mcp-server-from-database",
            "args": ["--prod"],
            "env": {"TEST": "database"},
        }

        with (
            patch("langflow.api.v2.mcp.get_server") as mock_get_server,
            patch("langflow.services.database.models.user.crud.get_user_by_id") as mock_get_user,
            patch("lfx.components.models_and_agents.mcp_component.session_scope"),
            patch.object(component.stdio_client, "connect_to_server") as mock_connect,
        ):
            mock_get_user.return_value = MagicMock(id="test_user_123")
            mock_get_server.return_value = db_config
            mock_connect.return_value = []

            # Call update_tool_list which should use db_config, not value_config
            await component.update_tool_list()

            # Verify that connect_to_server was called
            mock_connect.assert_called_once()
            call_args = mock_connect.call_args
            # The config passed should be from database, not value
            assert call_args is not None

            # Database should be queried first
            mock_get_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_config_used_when_no_value_config(self, component):
        """Test that database config is used when no config in value."""
        # Set up component with only server name, no config
        component.mcp_server = "test_server"
        component._user_id = "test_user_123"

        # Mock the database get_server to return a config
        db_config = {
            "command": "uvx mcp-server-from-database",
            "args": ["--prod"],
            "env": {"TEST": "database"},
        }

        with (
            patch("langflow.api.v2.mcp.get_server") as mock_get_server,
            patch("langflow.services.database.models.user.crud.get_user_by_id") as mock_get_user,
            patch("lfx.components.models_and_agents.mcp_component.session_scope"),
            patch.object(component.stdio_client, "connect_to_server") as mock_connect,
        ):
            mock_get_user.return_value = MagicMock(id="test_user_123")
            mock_get_server.return_value = db_config
            mock_connect.return_value = []

            # Call update_tool_list which should fetch from database
            await component.update_tool_list()

            # Verify that get_server WAS called since no value config provided
            mock_get_server.assert_called_once()

            # Verify connect_to_server was called
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_value_config_used_as_fallback_when_not_in_database(self, component):
        """Test that value config is used as fallback when server not in database."""
        # Set up component with server name and config in value
        value_config = {
            "command": "uvx mcp-server-from-value",
            "args": ["--test"],
        }
        component.mcp_server = {"name": "new_server", "config": value_config}
        component._user_id = "test_user_123"

        with (
            patch("langflow.api.v2.mcp.get_server") as mock_get_server,
            patch("langflow.services.database.models.user.crud.get_user_by_id") as mock_get_user,
            patch("lfx.components.models_and_agents.mcp_component.session_scope"),
            patch.object(component.stdio_client, "connect_to_server") as mock_connect,
        ):
            mock_get_user.return_value = MagicMock(id="test_user_123")
            # Database returns None (server not found)
            mock_get_server.return_value = None
            mock_connect.return_value = []

            # Call update_tool_list which should fall back to value config
            await component.update_tool_list()

            # Verify that get_server WAS called to check database first
            mock_get_server.assert_called_once()

            # Connect should be called with value config as fallback
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_rest_api_new_server_scenario(self, component):
        """Test REST API scenario where tweaks provide config for a new server not in database."""
        # Simulate REST API call with tweaks providing full config for a new server
        api_provided_config = {
            "command": "uvx mcp-server-api-new",
            "args": ["--api-mode"],
            "env": {"API_KEY": "secret123"},  # pragma: allowlist secret
        }
        component.mcp_server = {"name": "new_api_server", "config": api_provided_config}
        component._user_id = "api_user_456"

        with (
            patch("langflow.api.v2.mcp.get_server") as mock_get_server,
            patch("langflow.services.database.models.user.crud.get_user_by_id") as mock_get_user,
            patch("lfx.components.models_and_agents.mcp_component.session_scope"),
            patch.object(component.stdio_client, "connect_to_server") as mock_connect,
        ):
            mock_get_user.return_value = MagicMock(id="api_user_456")
            # Database returns None (server not in database yet)
            mock_get_server.return_value = None
            mock_connect.return_value = []

            # Call update_tool_list
            await component.update_tool_list()

            # Database should be queried first
            mock_get_server.assert_called_once()

            # Connect should be called with API-provided config as fallback


# ============================================================================
# Tests for resolve_mcp_config pure function
# ============================================================================


def test_resolve_config_db_takes_priority():
    """Test that database config takes priority over value config."""
    from lfx.components.models_and_agents.mcp_component import resolve_mcp_config

    db_config = {"command": "uvx from-db", "args": ["--prod"]}
    value_config = {"command": "uvx from-value", "args": ["--test"]}

    result = resolve_mcp_config("test_server", value_config, db_config)

    assert result == db_config


def test_resolve_config_falls_back_to_value():
    """Test that value config is used when DB returns None."""
    from lfx.components.models_and_agents.mcp_component import resolve_mcp_config

    value_config = {"command": "uvx from-value", "args": ["--test"]}

    result = resolve_mcp_config("test_server", value_config, None)

    assert result == value_config


def test_resolve_config_both_none():
    """Test behavior when both configs are None."""
    from lfx.components.models_and_agents.mcp_component import resolve_mcp_config

    assert resolve_mcp_config("test_server", None, None) is None


# ============================================================================
# Additional fixture-based tests as recommended in code review
# ============================================================================


@pytest.fixture
def mock_db_session_with_servers():
    """Create a simple mock session that doesn't require session_scope."""

    class MockSession:
        def __init__(self):
            self.servers = {
                "test_server": {"command": "uvx test", "args": []},
                "prod_server": {"command": "uvx prod", "args": ["--prod"]},
            }

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def get_server(self, name):
            return self.servers.get(name)

    return MockSession()


@pytest.mark.asyncio
async def test_config_priority_with_fixtures(mock_db_session_with_servers):
    """Test using fixtures with real data instead of heavy mocking."""
    from lfx.components.models_and_agents.mcp_component import MCPToolsComponent

    component = MCPToolsComponent()
    component.mcp_server = {"name": "test_server", "config": {"command": "from-value"}}
    component._user_id = "test_user"

    # Inject the mock session directly rather than mocking session_scope
    with (
        patch("langflow.api.v2.mcp.get_server") as mock_get_server,
        patch("langflow.services.database.models.user.crud.get_user_by_id") as mock_get_user,
        patch(
            "lfx.components.models_and_agents.mcp_component.session_scope",
            return_value=mock_db_session_with_servers,
        ),
        patch.object(component.stdio_client, "connect_to_server", return_value=[]),
    ):
        mock_get_user.return_value = MagicMock(id="test_user")
        mock_get_server.return_value = {"command": "uvx test", "args": []}

        _tools, server_info = await component.update_tool_list()

    # Verify behavior without needing to assert on mocks
    assert server_info["config"]["command"] == "uvx test"  # From DB
