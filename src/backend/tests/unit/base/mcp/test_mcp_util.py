"""Unit tests for MCP utility functions.

This test suite validates the MCP utility functions including:
- Session management
- Header validation and processing
- Utility functions for name sanitization and schema conversion
"""

import shutil
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.base.mcp import util
from langflow.base.mcp.util import MCPSessionManager, MCPSseClient, MCPStdioClient, _process_headers, validate_headers


class TestMCPSessionManager:
    @pytest.fixture
    async def session_manager(self):
        """Create a session manager and clean it up after the test."""
        manager = MCPSessionManager()
        yield manager
        # Clean up after test
        await manager.cleanup_all()

    async def test_session_caching(self, session_manager):
        """Test that sessions are properly cached and reused."""
        context_id = "test_context"
        connection_params = MagicMock()
        transport_type = "stdio"

        # Create a mock session that will appear healthy
        mock_session = AsyncMock()
        mock_session._write_stream = MagicMock()
        mock_session._write_stream._closed = False

        # Create a mock task that appears to be running
        mock_task = AsyncMock()
        mock_task.done = MagicMock(return_value=False)

        with (
            patch.object(session_manager, "_create_stdio_session") as mock_create,
            patch.object(session_manager, "_validate_session_connectivity", return_value=True),
        ):
            mock_create.return_value = (mock_session, mock_task)

            # First call should create session
            session1 = await session_manager.get_session(context_id, connection_params, transport_type)

            # Second call should return cached session without creating new one
            session2 = await session_manager.get_session(context_id, connection_params, transport_type)

            assert session1 == session2
            assert session1 == mock_session
            # Should only create once since the second call should use the cached session
            mock_create.assert_called_once()

    async def test_session_cleanup(self, session_manager):
        """Test session cleanup functionality."""
        context_id = "test_context"
        server_key = "test_server"
        session_id = "test_session"

        # Add a session to the manager with proper mock setup using new structure
        mock_task = AsyncMock()
        mock_task.done = MagicMock(return_value=False)  # Use MagicMock for sync method
        mock_task.cancel = MagicMock()  # Use MagicMock for sync method

        # Set up the new session structure
        session_manager.sessions_by_server[server_key] = {
            "sessions": {session_id: {"session": AsyncMock(), "task": mock_task, "type": "stdio", "last_used": 0}},
            "last_cleanup": 0,
        }

        # Set up mapping for backwards compatibility
        session_manager._context_to_session[context_id] = (server_key, session_id)

        await session_manager._cleanup_session(context_id)

        # Should cancel the task and remove from sessions
        mock_task.cancel.assert_called_once()
        assert session_id not in session_manager.sessions_by_server[server_key]["sessions"]

    async def test_server_switch_detection(self, session_manager):
        """Test that server switches are properly detected and handled."""
        context_id = "test_context"

        # First server
        server1_params = MagicMock()
        server1_params.command = "server1"

        # Second server
        server2_params = MagicMock()
        server2_params.command = "server2"

        with (
            patch.object(session_manager, "_create_stdio_session") as mock_create,
            patch.object(session_manager, "_validate_session_connectivity", return_value=True),
        ):
            mock_session1 = AsyncMock()
            mock_session2 = AsyncMock()
            mock_task1 = AsyncMock()
            mock_task2 = AsyncMock()
            mock_create.side_effect = [(mock_session1, mock_task1), (mock_session2, mock_task2)]

            # First connection
            session1 = await session_manager.get_session(context_id, server1_params, "stdio")

            # Switch to different server should create new session
            session2 = await session_manager.get_session(context_id, server2_params, "stdio")

            assert session1 != session2
            assert mock_create.call_count == 2


class TestHeaderValidation:
    """Test the header validation functionality."""

    def test_validate_headers_valid_input(self):
        """Test header validation with valid headers."""
        headers = {"Authorization": "Bearer token123", "Content-Type": "application/json", "X-API-Key": "secret-key"}

        result = validate_headers(headers)

        # Headers should be normalized to lowercase
        expected = {"authorization": "Bearer token123", "content-type": "application/json", "x-api-key": "secret-key"}
        assert result == expected

    def test_validate_headers_empty_input(self):
        """Test header validation with empty/None input."""
        assert validate_headers({}) == {}
        assert validate_headers(None) == {}

    def test_validate_headers_invalid_names(self):
        """Test header validation with invalid header names."""
        headers = {
            "Invalid Header": "value",  # spaces not allowed
            "Header@Name": "value",  # @ not allowed
            "Header Name": "value",  # spaces not allowed
            "Valid-Header": "value",  # this should pass
        }

        result = validate_headers(headers)

        # Only the valid header should remain
        assert result == {"valid-header": "value"}

    def test_validate_headers_sanitize_values(self):
        """Test header value sanitization."""
        headers = {
            "Authorization": "Bearer \x00token\x1f with\r\ninjection",
            "Clean-Header": "  clean value  ",
            "Empty-After-Clean": "\x00\x01\x02",
            "Tab-Header": "value\twith\ttabs",  # tabs should be preserved
        }

        result = validate_headers(headers)

        # Control characters should be removed, whitespace trimmed
        # Header with injection attempts should be skipped
        expected = {"clean-header": "clean value", "tab-header": "value\twith\ttabs"}
        assert result == expected

    def test_validate_headers_non_string_values(self):
        """Test header validation with non-string values."""
        headers = {"String-Header": "valid", "Number-Header": 123, "None-Header": None, "List-Header": ["value"]}

        result = validate_headers(headers)

        # Only string headers should remain
        assert result == {"string-header": "valid"}

    def test_validate_headers_injection_attempts(self):
        """Test header validation against injection attempts."""
        headers = {
            "Injection1": "value\r\nInjected-Header: malicious",
            "Injection2": "value\nX-Evil: attack",
            "Safe-Header": "safe-value",
        }

        result = validate_headers(headers)

        # Injection attempts should be filtered out
        assert result == {"safe-header": "safe-value"}


class TestSSEHeaderIntegration:
    """Integration test to verify headers are properly passed through the entire SSE flow."""

    async def test_headers_processing(self):
        """Test that headers flow properly from server config through to SSE client connection."""
        # Test the header processing function directly
        headers_input = [
            {"key": "Authorization", "value": "Bearer test-token"},
            {"key": "X-API-Key", "value": "secret-key"},
        ]

        expected_headers = {
            "authorization": "Bearer test-token",  # normalized to lowercase
            "x-api-key": "secret-key",
        }

        # Test _process_headers function with validation
        processed_headers = _process_headers(headers_input)
        assert processed_headers == expected_headers

        # Test different input formats
        # Test dict input with validation
        dict_headers = {"Authorization": "Bearer dict-token", "Invalid Header": "bad"}
        result = _process_headers(dict_headers)
        # Invalid header should be filtered out, valid header normalized
        assert result == {"authorization": "Bearer dict-token"}

        # Test None input
        assert _process_headers(None) == {}

        # Test empty list
        assert _process_headers([]) == {}

        # Test malformed list
        malformed_headers = [{"key": "Auth"}, {"value": "token"}]  # Missing value/key
        assert _process_headers(malformed_headers) == {}

        # Test list with invalid header names
        invalid_headers = [
            {"key": "Valid-Header", "value": "good"},
            {"key": "Invalid Header", "value": "bad"},  # spaces not allowed
        ]
        result = _process_headers(invalid_headers)
        assert result == {"valid-header": "good"}

    async def test_sse_client_header_storage(self):
        """Test that SSE client properly stores headers in connection params."""
        sse_client = MCPSseClient()
        test_url = "http://test.url"
        test_headers = {"Authorization": "Bearer test123", "Custom": "value"}

        # Test that headers are properly stored in connection params
        # Set connection params as a dict like the implementation expects
        sse_client._connection_params = {
            "url": test_url,
            "headers": test_headers,
            "timeout_seconds": 30,
            "sse_read_timeout_seconds": 30,
        }

        # Verify headers are stored
        assert sse_client._connection_params["url"] == test_url
        assert sse_client._connection_params["headers"] == test_headers


class TestMCPUtilityFunctions:
    """Test utility functions from util.py that don't have dedicated test classes."""

    def test_sanitize_mcp_name(self):
        """Test MCP name sanitization."""
        assert util.sanitize_mcp_name("Test Name 123") == "test_name_123"
        assert util.sanitize_mcp_name("  ") == ""
        assert util.sanitize_mcp_name("123abc") == "_123abc"
        assert util.sanitize_mcp_name("Tést-😀-Námé") == "test_name"
        assert util.sanitize_mcp_name("a" * 100) == "a" * 46

    def test_get_unique_name(self):
        """Test unique name generation."""
        names = {"foo", "foo_1"}
        assert util.get_unique_name("foo", 10, names) == "foo_2"
        assert util.get_unique_name("bar", 10, names) == "bar"
        assert util.get_unique_name("longname", 4, {"long"}) == "lo_1"

    def test_is_valid_key_value_item(self):
        """Test key-value item validation."""
        assert util._is_valid_key_value_item({"key": "a", "value": "b"}) is True
        assert util._is_valid_key_value_item({"key": "a"}) is False
        assert util._is_valid_key_value_item(["key", "value"]) is False
        assert util._is_valid_key_value_item(None) is False

    def test_validate_node_installation(self):
        """Test Node.js installation validation."""
        if shutil.which("node"):
            assert util._validate_node_installation("npx something") == "npx something"
        else:
            with pytest.raises(ValueError, match="Node.js is not installed"):
                util._validate_node_installation("npx something")
        assert util._validate_node_installation("echo test") == "echo test"

    def test_create_input_schema_from_json_schema(self):
        """Test JSON schema to Pydantic model conversion."""
        schema = {
            "type": "object",
            "properties": {
                "foo": {"type": "string", "description": "desc"},
                "bar": {"type": "integer"},
            },
            "required": ["foo"],
        }
        model_class = util.create_input_schema_from_json_schema(schema)
        instance = model_class(foo="abc", bar=1)
        assert instance.foo == "abc"
        assert instance.bar == 1

        with pytest.raises(Exception):  # noqa: B017, PT011
            model_class(bar=1)  # missing required field

    @pytest.mark.asyncio
    async def test_validate_connection_params(self):
        """Test connection parameter validation."""
        # Valid parameters
        await util._validate_connection_params("Stdio", command="echo test")
        await util._validate_connection_params("SSE", url="http://test")

        # Invalid parameters
        with pytest.raises(ValueError, match="Command is required for Stdio mode"):
            await util._validate_connection_params("Stdio", command=None)
        with pytest.raises(ValueError, match="URL is required for SSE mode"):
            await util._validate_connection_params("SSE", url=None)
        with pytest.raises(ValueError, match="Invalid mode"):
            await util._validate_connection_params("InvalidMode")

    @pytest.mark.asyncio
    async def test_get_flow_snake_case_mocked(self):
        """Test flow lookup by snake case name with mocked session."""

        class DummyFlow:
            def __init__(self, name: str, user_id: str, *, is_component: bool = False, action_name: str | None = None):
                self.name = name
                self.user_id = user_id
                self.is_component = is_component
                self.action_name = action_name

        class DummyExec:
            def __init__(self, flows: list[DummyFlow]):
                self._flows = flows

            def all(self):
                return self._flows

        class DummySession:
            def __init__(self, flows: list[DummyFlow]):
                self._flows = flows

            async def exec(self, stmt):  # noqa: ARG002
                return DummyExec(self._flows)

        user_id = "123e4567-e89b-12d3-a456-426614174000"
        flows = [DummyFlow("Test Flow", user_id), DummyFlow("Other", user_id)]

        # Should match sanitized name
        result = await util.get_flow_snake_case(util.sanitize_mcp_name("Test Flow"), user_id, DummySession(flows))
        assert result is flows[0]

        # Should return None if not found
        result = await util.get_flow_snake_case("notfound", user_id, DummySession(flows))
        assert result is None


class TestMCPStdioClientWithEverythingServer:
    """Test MCPStdioClient with the Everything MCP server."""

    @pytest.fixture
    def stdio_client(self):
        """Create a stdio client for testing."""
        return MCPStdioClient()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
    async def test_connect_to_everything_server(self, stdio_client):
        """Test connecting to the Everything MCP server."""
        command = "npx -y @modelcontextprotocol/server-everything"

        try:
            # Connect to the server
            tools = await stdio_client.connect_to_server(command)

            # Verify tools were returned
            assert len(tools) > 0

            # Find the echo tool
            echo_tool = None
            for tool in tools:
                if hasattr(tool, "name") and tool.name == "echo":
                    echo_tool = tool
                    break

            assert echo_tool is not None, "Echo tool not found in server tools"
            assert echo_tool.description is not None

            # Verify the echo tool has the expected input schema
            assert hasattr(echo_tool, "inputSchema")
            assert echo_tool.inputSchema is not None

        finally:
            # Clean up the connection
            await stdio_client.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
    async def test_run_echo_tool(self, stdio_client):
        """Test running the echo tool from the Everything server."""
        command = "npx -y @modelcontextprotocol/server-everything"

        try:
            # Connect to the server
            tools = await stdio_client.connect_to_server(command)

            # Find the echo tool
            echo_tool = None
            for tool in tools:
                if hasattr(tool, "name") and tool.name == "echo":
                    echo_tool = tool
                    break

            assert echo_tool is not None, "Echo tool not found"

            # Run the echo tool
            test_message = "Hello, MCP!"
            result = await stdio_client.run_tool("echo", {"message": test_message})

            # Verify the result
            assert result is not None
            assert hasattr(result, "content")
            assert len(result.content) > 0

            # Check that the echo worked - content should contain our message
            content_text = str(result.content[0])
            assert test_message in content_text or "Echo:" in content_text

        finally:
            await stdio_client.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
    async def test_list_all_tools(self, stdio_client):
        """Test listing all available tools from the Everything server."""
        command = "npx -y @modelcontextprotocol/server-everything"

        try:
            # Connect to the server
            tools = await stdio_client.connect_to_server(command)

            # Verify we have multiple tools
            assert len(tools) >= 3  # Everything server typically has several tools

            # Check that tools have the expected attributes
            for tool in tools:
                assert hasattr(tool, "name")
                assert hasattr(tool, "description")
                assert hasattr(tool, "inputSchema")
                assert tool.name is not None
                assert len(tool.name) > 0

            # Common tools that should be available
            expected_tools = ["echo"]  # Echo is typically available
            for expected_tool in expected_tools:
                assert any(tool.name == expected_tool for tool in tools), f"Expected tool '{expected_tool}' not found"

        finally:
            await stdio_client.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
    async def test_session_reuse(self, stdio_client):
        """Test that sessions are properly reused."""
        command = "npx -y @modelcontextprotocol/server-everything"

        try:
            # Set session context
            stdio_client.set_session_context("test_session_reuse")

            # Connect to the server
            tools1 = await stdio_client.connect_to_server(command)

            # Connect again - should reuse the session
            tools2 = await stdio_client.connect_to_server(command)

            # Should have the same tools
            assert len(tools1) == len(tools2)

            # Run a tool to verify the session is working
            result = await stdio_client.run_tool("echo", {"message": "Session reuse test"})
            assert result is not None

        finally:
            await stdio_client.disconnect()


class TestMCPSseClientWithDeepWikiServer:
    """Test MCPSseClient with the DeepWiki MCP server."""

    @pytest.fixture
    def sse_client(self):
        """Create an SSE client for testing."""
        return MCPSseClient()

    @pytest.mark.asyncio
    async def test_connect_to_deepwiki_server(self, sse_client):
        """Test connecting to the DeepWiki MCP server."""
        url = "https://mcp.deepwiki.com/sse"

        try:
            # Connect to the server
            tools = await sse_client.connect_to_server(url)

            # Verify tools were returned
            assert len(tools) > 0

            # Check for expected DeepWiki tools
            expected_tools = ["read_wiki_structure", "read_wiki_contents", "ask_question"]

            # Verify we have the expected tools
            for expected_tool in expected_tools:
                assert any(tool.name == expected_tool for tool in tools), f"Expected tool '{expected_tool}' not found"

        except Exception as e:
            # If the server is not accessible, skip the test
            pytest.skip(f"DeepWiki server not accessible: {e}")
        finally:
            await sse_client.disconnect()

    @pytest.mark.asyncio
    async def test_run_wiki_structure_tool(self, sse_client):
        """Test running the read_wiki_structure tool."""
        url = "https://mcp.deepwiki.com/sse"

        try:
            # Connect to the server
            tools = await sse_client.connect_to_server(url)

            # Find the read_wiki_structure tool
            wiki_tool = None
            for tool in tools:
                if hasattr(tool, "name") and tool.name == "read_wiki_structure":
                    wiki_tool = tool
                    break

            assert wiki_tool is not None, "read_wiki_structure tool not found"

            # Run the tool with a test repository (use repoName as expected by the API)
            result = await sse_client.run_tool("read_wiki_structure", {"repoName": "microsoft/vscode"})

            # Verify the result
            assert result is not None
            assert hasattr(result, "content")
            assert len(result.content) > 0

        except Exception as e:
            # If the server is not accessible or the tool fails, skip the test
            pytest.skip(f"DeepWiki server test failed: {e}")
        finally:
            await sse_client.disconnect()

    @pytest.mark.asyncio
    async def test_ask_question_tool(self, sse_client):
        """Test running the ask_question tool."""
        url = "https://mcp.deepwiki.com/sse"

        try:
            # Connect to the server
            tools = await sse_client.connect_to_server(url)

            # Find the ask_question tool
            ask_tool = None
            for tool in tools:
                if hasattr(tool, "name") and tool.name == "ask_question":
                    ask_tool = tool
                    break

            assert ask_tool is not None, "ask_question tool not found"

            # Run the tool with a test question (use repoName as expected by the API)
            result = await sse_client.run_tool(
                "ask_question", {"repoName": "microsoft/vscode", "question": "What is VS Code?"}
            )

            # Verify the result
            assert result is not None
            assert hasattr(result, "content")
            assert len(result.content) > 0

        except Exception as e:
            # If the server is not accessible or the tool fails, skip the test
            pytest.skip(f"DeepWiki server test failed: {e}")
        finally:
            await sse_client.disconnect()

    @pytest.mark.asyncio
    async def test_url_validation(self, sse_client):
        """Test URL validation for SSE connections."""
        # Test valid URL
        valid_url = "https://mcp.deepwiki.com/sse"
        is_valid, error = await sse_client.validate_url(valid_url)
        assert is_valid or error == ""  # Either valid or accessible

        # Test invalid URL
        invalid_url = "not_a_url"
        is_valid, error = await sse_client.validate_url(invalid_url)
        assert not is_valid
        assert error != ""

    @pytest.mark.asyncio
    async def test_redirect_handling(self, sse_client):
        """Test redirect handling for SSE connections."""
        # Test with the DeepWiki URL
        url = "https://mcp.deepwiki.com/sse"

        try:
            # Check for redirects
            final_url = await sse_client.pre_check_redirect(url)

            # Should return a URL (either original or redirected)
            assert final_url is not None
            assert isinstance(final_url, str)
            assert final_url.startswith("http")

        except Exception as e:
            # If the server is not accessible, skip the test
            pytest.skip(f"DeepWiki server not accessible for redirect test: {e}")

    @pytest.fixture
    def mock_tool(self):
        """Create a mock MCP tool."""
        tool = MagicMock()
        tool.name = "test_tool"
        tool.description = "Test tool description"
        tool.inputSchema = {
            "type": "object",
            "properties": {"test_param": {"type": "string", "description": "Test parameter"}},
            "required": ["test_param"],
        }
        return tool

    @pytest.fixture
    def mock_session(self, mock_tool):
        """Create a mock ClientSession."""
        session = AsyncMock()
        session.initialize = AsyncMock()
        list_tools_result = MagicMock()
        list_tools_result.tools = [mock_tool]
        session.list_tools = AsyncMock(return_value=list_tools_result)
        session.call_tool = AsyncMock(
            return_value=MagicMock(content=[MagicMock(model_dump=lambda: {"result": "success"})])
        )
        return session


class TestMCPSseClientUnit:
    """Unit tests for MCPSseClient functionality."""

    @pytest.fixture
    def sse_client(self):
        return MCPSseClient()

    @pytest.mark.asyncio
    async def test_client_initialization(self, sse_client):
        """Test that SSE client initializes correctly."""
        # Client should initialize with default values
        assert sse_client.session is None
        assert sse_client._connection_params is None
        assert sse_client._connected is False
        assert sse_client._session_context is None

    async def test_validate_url_valid(self, sse_client):
        """Test URL validation with valid URL."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

            is_valid, error_msg = await sse_client.validate_url("http://test.url", {})

            assert is_valid is True
            assert error_msg == ""

    async def test_validate_url_invalid_format(self, sse_client):
        """Test URL validation with invalid format."""
        is_valid, error_msg = await sse_client.validate_url("invalid-url", {})

        assert is_valid is False
        assert "Invalid URL format" in error_msg

    async def test_validate_url_with_404_response(self, sse_client):
        """Test URL validation with 404 response (should be valid for SSE)."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

            is_valid, error_msg = await sse_client.validate_url("http://test.url", {})

            assert is_valid is True
            assert error_msg == ""

    async def test_connect_to_server_with_headers(self, sse_client):
        """Test connecting to server via SSE with custom headers."""
        test_url = "http://test.url"
        test_headers = {"Authorization": "Bearer token123", "Custom-Header": "value"}
        expected_headers = {"authorization": "Bearer token123", "custom-header": "value"}  # normalized

        with (
            patch.object(sse_client, "validate_url", return_value=(True, "")),
            patch.object(sse_client, "pre_check_redirect", return_value=test_url),
            patch.object(sse_client, "_get_or_create_session") as mock_get_session,
        ):
            # Mock session
            mock_session = AsyncMock()
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            list_tools_result = MagicMock()
            list_tools_result.tools = [mock_tool]
            mock_session.list_tools = AsyncMock(return_value=list_tools_result)
            mock_get_session.return_value = mock_session

            tools = await sse_client.connect_to_server(test_url, test_headers)

            assert len(tools) == 1
            assert tools[0].name == "test_tool"
            assert sse_client._connected is True

            # Verify headers are stored in connection params (normalized)
            assert sse_client._connection_params is not None
            assert sse_client._connection_params["headers"] == expected_headers
            assert sse_client._connection_params["url"] == test_url

    async def test_headers_passed_to_session_manager(self, sse_client):
        """Test that headers are properly passed to the session manager."""
        test_url = "http://test.url"
        expected_headers = {"authorization": "Bearer token123", "x-api-key": "secret"}  # normalized

        sse_client._session_context = "test_context"
        sse_client._connection_params = {
            "url": test_url,
            "headers": expected_headers,  # Use normalized headers
            "timeout_seconds": 30,
            "sse_read_timeout_seconds": 30,
        }

        with patch.object(sse_client, "_get_session_manager") as mock_get_manager:
            mock_manager = AsyncMock()
            mock_session = AsyncMock()
            mock_manager.get_session = AsyncMock(return_value=mock_session)
            mock_get_manager.return_value = mock_manager

            result_session = await sse_client._get_or_create_session()

            # Verify session manager was called with correct parameters including normalized headers
            mock_manager.get_session.assert_called_once_with("test_context", sse_client._connection_params, "sse")
            assert result_session == mock_session

    async def test_pre_check_redirect_with_headers(self, sse_client):
        """Test pre-check redirect functionality with custom headers."""
        test_url = "http://test.url"
        redirect_url = "http://redirect.url"
        # Use pre-validated headers since pre_check_redirect expects already validated headers
        test_headers = {"authorization": "Bearer token123"}  # already normalized

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 307
            mock_response.headers.get.return_value = redirect_url
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

            result = await sse_client.pre_check_redirect(test_url, test_headers)

            assert result == redirect_url
            # Verify validated headers were passed to the request
            mock_client.return_value.__aenter__.return_value.get.assert_called_with(
                test_url, timeout=2.0, headers={"Accept": "text/event-stream", **test_headers}
            )

    async def test_run_tool_with_retry_on_connection_error(self, sse_client):
        """Test that run_tool retries on connection errors."""
        # Setup connection state
        sse_client._connected = True
        sse_client._connection_params = {"url": "http://test.url", "headers": {}}
        sse_client._session_context = "test_context"

        call_count = 0

        async def mock_get_session_side_effect():
            nonlocal call_count
            call_count += 1
            session = AsyncMock()
            if call_count == 1:
                # First call fails with connection error
                from anyio import ClosedResourceError

                session.call_tool = AsyncMock(side_effect=ClosedResourceError())
            else:
                # Second call succeeds
                mock_result = MagicMock()
                session.call_tool = AsyncMock(return_value=mock_result)
            return session

        with (
            patch.object(sse_client, "_get_or_create_session", side_effect=mock_get_session_side_effect),
            patch.object(sse_client, "_get_session_manager") as mock_get_manager,
        ):
            mock_manager = AsyncMock()
            mock_get_manager.return_value = mock_manager

            result = await sse_client.run_tool("test_tool", {"param": "value"})

            # Should have retried and succeeded on second attempt
            assert call_count == 2
            assert result is not None
            # Should have cleaned up the failed session
            mock_manager._cleanup_session.assert_called_once_with("test_context")
